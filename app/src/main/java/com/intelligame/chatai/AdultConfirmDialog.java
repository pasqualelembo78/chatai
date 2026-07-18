package com.intelligame.chatai;

import android.app.Dialog;
import android.content.Context;
import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.widget.Button;
import android.widget.TextView;

import org.json.JSONObject;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.appcompat.app.AlertDialog;
import androidx.fragment.app.DialogFragment;

import com.google.android.material.textfield.TextInputEditText;

import java.util.Calendar;

public class AdultConfirmDialog extends DialogFragment {

    private final OnConfirmListener listener;

    public interface OnConfirmListener {
        void onConfirmed();
    }

    public AdultConfirmDialog(OnConfirmListener listener) {
        this.listener = listener;
    }

    @NonNull
    @Override
    public Dialog onCreateDialog(@Nullable Bundle savedInstanceState) {
        AlertDialog.Builder builder = new AlertDialog.Builder(requireActivity(), R.style.Theme_Transparent);
        LayoutInflater inflater = requireActivity().getLayoutInflater();
        View view = inflater.inflate(R.layout.dialog_adult_confirm, null);

        TextInputEditText birthYearInput = view.findViewById(R.id.et_birth_year);
        TextView errorText = view.findViewById(R.id.adult_error_text);
        Button cancelBtn = view.findViewById(R.id.btn_adult_cancel);
        Button confirmBtn = view.findViewById(R.id.btn_adult_confirm);

        cancelBtn.setOnClickListener(v -> dismiss());
        confirmBtn.setOnClickListener(v -> {
            String yearStr = birthYearInput.getText().toString().trim();
            if (yearStr.isEmpty()) {
                errorText.setText("Inserisci il tuo anno di nascita");
                errorText.setVisibility(View.VISIBLE);
                return;
            }
            int currentYear = Calendar.getInstance().get(Calendar.YEAR);
            int birthYear;
            try {
                birthYear = Integer.parseInt(yearStr);
            } catch (NumberFormatException e) {
                errorText.setText("Anno non valido");
                errorText.setVisibility(View.VISIBLE);
                return;
            }
            if (birthYear < 1900 || birthYear > currentYear) {
                errorText.setText("Inserisci un anno valido (1900-" + currentYear + ")");
                errorText.setVisibility(View.VISIBLE);
                return;
            }
            int age = currentYear - birthYear;
            if (age < 18) {
                errorText.setText("Devi avere almeno 18 anni per accedere a questo contenuto");
                errorText.setVisibility(View.VISIBLE);
                return;
            }

            // Salva la verifica età in locale (cache UX) e la registra lato server.
            // Il gate 18+ e' fatto valere sul server: i contenuti per adulti non sono
            // raggiungibili da minori nemmeno modificando le preferenze locali.
            Context ctx = requireContext();
            ChatApplication app = ctx != null ? (ChatApplication) ctx.getApplicationContext() : null;
            if (app != null) {
                app.getPrefs().setAdultBirthYear(birthYear);
                final int finalBirthYear = birthYear;
                new Thread(() -> {
                    try {
                        JSONObject body = new JSONObject();
                        body.put("birth_year", finalBirthYear);
                        app.getAuthManager().requestWithRefresh(
                                app.getPrefs().getServerUrl() + "/me/verify-age",
                                "POST", body.toString(), 8000);
                    } catch (Exception ignored) {}
                }).start();
            }

            if (listener != null) {
                listener.onConfirmed();
            }
            dismiss();
        });

        builder.setView(view);
        return builder.create();
    }
}
