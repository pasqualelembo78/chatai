package com.intelligame.chatadmin;

import android.content.Intent;
import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.Fragment;

import org.json.JSONArray;
import org.json.JSONObject;

public class ImportFragment extends Fragment {

    private AuthManager mAuth;

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater, @Nullable ViewGroup container, @Nullable Bundle savedInstanceState) {
        return inflater.inflate(R.layout.fragment_import, container, false);
    }

    @Override
    public void onViewCreated(@NonNull View view, @Nullable Bundle savedInstanceState) {
        super.onViewCreated(view, savedInstanceState);
        mAuth = ((ChatApplication) requireActivity().getApplication()).getAuthManager();

        view.findViewById(R.id.btn_open_import).setOnClickListener(v -> {
            startActivity(new Intent(getContext(), ImportActivity.class));
        });

        view.findViewById(R.id.btn_scan_chars).setOnClickListener(v -> scanCharacters());
    }

    private void scanCharacters() {
        TextView countView = getView().findViewById(R.id.chars_count);
        countView.setText("Scansione in corso...");
        new Thread(() -> {
            try {
                String url = ((ChatApplication) requireActivity().getApplication()).getCurrentUrl() + "/admin/characters";
                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(url, "GET", null, 10000);
                if (resp.statusCode == 200) {
                    JSONArray arr = new JSONArray(resp.body);
                    if (getActivity() != null) {
                        getActivity().runOnUiThread(() ->
                            countView.setText("Personaggi utente trovati: " + arr.length()));
                    }
                }
            } catch (Exception e) {
                if (getActivity() != null) {
                    getActivity().runOnUiThread(() ->
                        Toast.makeText(getContext(), "Errore scansione", Toast.LENGTH_SHORT).show());
                }
            }
        }).start();
    }
}
