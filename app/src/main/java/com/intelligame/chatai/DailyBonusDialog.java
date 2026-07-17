package com.intelligame.chatai;

import android.app.AlertDialog;
import android.app.Dialog;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.DialogFragment;

import org.json.JSONObject;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class DailyBonusDialog extends DialogFragment {

    private static final String TAG = "DailyBonusDialog";
    private ExecutorService executor = new SafeExecutor();
    private Handler mainHandler = new Handler(Looper.getMainLooper());

    @NonNull
    @Override
    public Dialog onCreateDialog(@Nullable Bundle savedInstanceState) {
        View view = requireActivity().getLayoutInflater().inflate(R.layout.dialog_daily_bonus, null);
        
        TextView titleText = view.findViewById(R.id.bonus_title);
        TextView rewardText = view.findViewById(R.id.bonus_reward_text);
        TextView streakText = view.findViewById(R.id.bonus_streak_text);
        
        titleText.setText("Bonus Giornaliero!");
        rewardText.setText("Caricamento...");
        streakText.setText("");

        checkAndShowBonus(view);

        AlertDialog.Builder builder = new AlertDialog.Builder(requireActivity());
        builder.setView(view)
               .setPositiveButton("Riscuoti", (dialog, which) -> claimDailyBonus())
               .setNegativeButton("Più tardi", (dialog, which) -> dialog.dismiss());
        
        AlertDialog dialog = builder.create();
        dialog.setCancelable(false);
        return dialog;
    }

    private void checkAndShowBonus(View view) {
        TextView rewardText = view.findViewById(R.id.bonus_reward_text);
        TextView streakText = view.findViewById(R.id.bonus_streak_text);

        executor.execute(() -> {
            try {
                ChatApplication app = (ChatApplication) requireActivity().getApplication();
                AuthManager auth = app.getAuthManager();
                String baseUrl = app.getPrefs().getServerUrl().replace("/chat", "");

                AuthManager.HttpResponse httpResp = auth.requestWithRefresh(baseUrl + "/user/mevacoins/streak", "GET", null, 5000);

                if (httpResp.statusCode == 200) {
                    JSONObject result = new JSONObject(httpResp.body);
                    int currentDay = result.optInt("current_day", 1);
                    boolean alreadyClaimed = result.optBoolean("already_claimed_today", false);
                    int reward = calculateReward(currentDay);

                    mainHandler.post(() -> {
                        if (isAdded()) {
                            if (alreadyClaimed) {
                                rewardText.setText("✓ Già riscosso oggi!");
                                streakText.setText("Torna domani per il giorno " + (currentDay + 1));
                                if (getDialog() != null) {
                                    ((AlertDialog) getDialog()).getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(false);
                                }
                            } else {
                                rewardText.setText("+" + reward + " MVC");
                                streakText.setText("Giorno " + currentDay + " di 30" +
                                    (currentDay == 30 ? "\nSUPER BONUS!" : ""));
                            }
                        }
                    });
                }
            } catch (Exception e) {
                mainHandler.post(() -> {
                    if (isAdded()) {
                        rewardText.setText("+10 MVC");
                        streakText.setText("Giorno 1 di 30");
                    }
                });
            }
        });
    }

    private void claimDailyBonus() {
        executor.execute(() -> {
            try {
                ChatApplication app = (ChatApplication) requireActivity().getApplication();
                AuthManager auth = app.getAuthManager();
                String baseUrl = app.getPrefs().getServerUrl().replace("/chat", "");

                JSONObject body = new JSONObject();
                body.put("day", 0);
                AuthManager.HttpResponse httpResp = auth.requestWithRefresh(baseUrl + "/user/mevacoins/streak/claim", "POST", body.toString(), 5000);

                if (httpResp.statusCode >= 200 && httpResp.statusCode < 300) {
                    JSONObject result = new JSONObject(httpResp.body);
                    int earned = result.optInt("earned", 10);

                    mainHandler.post(() -> {
                        if (isAdded()) {
                            if (getDialog() != null) getDialog().dismiss();
                            if (getActivity() != null) {
                                com.google.android.material.snackbar.Snackbar.make(
                                    getActivity().findViewById(android.R.id.content),
                                    "+" + earned + " MVC riscossi!",
                                    com.google.android.material.snackbar.Snackbar.LENGTH_LONG).show();
                            }
                        }
                    });
                } else {
                    mainHandler.post(() -> {
                        if (isAdded()) {
                            if (getDialog() != null) getDialog().dismiss();
                            if (getActivity() != null) {
                                com.google.android.material.snackbar.Snackbar.make(
                                    getActivity().findViewById(android.R.id.content),
                                    "Errore: riprova più tardi",
                                    com.google.android.material.snackbar.Snackbar.LENGTH_SHORT).show();
                            }
                        }
                    });
                }
            } catch (Exception e) {
                mainHandler.post(() -> {
                    if (isAdded() && getDialog() != null) getDialog().dismiss();
                });
            }
        });
    }

    private int calculateReward(int day) {
        if (day >= 30) return 100;
        return 10 + (day - 1) * 2;
    }

    @Override
    public void onDestroyView() {
        super.onDestroyView();
        if (executor != null) executor.shutdownNow();
    }
}
