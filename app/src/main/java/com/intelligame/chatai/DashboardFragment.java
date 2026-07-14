package com.intelligame.chatai;

import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.Fragment;

import org.json.JSONObject;

public class DashboardFragment extends Fragment {

    private AuthManager mAuth;
    private TextView statTotalUsers, statActive7d, statRegistrationsToday, statTotalMessages;
    private TextView statPendingFlags, statUserCharacters, statRegistrations7d, statActive30d;

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater, @Nullable ViewGroup container, @Nullable Bundle savedInstanceState) {
        return inflater.inflate(R.layout.fragment_dashboard, container, false);
    }

    @Override
    public void onViewCreated(@NonNull View view, @Nullable Bundle savedInstanceState) {
        super.onViewCreated(view, savedInstanceState);
        mAuth = ((ChatApplication) requireActivity().getApplication()).getAuthManager();

        statTotalUsers = view.findViewById(R.id.stat_total_users);
        statActive7d = view.findViewById(R.id.stat_active_7d);
        statRegistrationsToday = view.findViewById(R.id.stat_registrations_today);
        statTotalMessages = view.findViewById(R.id.stat_total_messages);
        statPendingFlags = view.findViewById(R.id.stat_pending_flags);
        statUserCharacters = view.findViewById(R.id.stat_user_characters);
        statRegistrations7d = view.findViewById(R.id.stat_registrations_7d);
        statActive30d = view.findViewById(R.id.stat_active_30d);

        view.findViewById(R.id.btn_refresh).setOnClickListener(v -> loadStats());
        loadStats();
    }

    private void loadStats() {
        new Thread(() -> {
            try {
                String url = ((ChatApplication) requireActivity().getApplication()).getCurrentUrl() + "/admin/stats";
                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(url, "GET", null, 10000);
                if (resp.statusCode == 200) {
                    JSONObject obj = new JSONObject(resp.body);
                    if (getActivity() != null) {
                        getActivity().runOnUiThread(() -> {
                            statTotalUsers.setText(String.valueOf(obj.optInt("total_users", 0)));
                            statActive7d.setText(String.valueOf(obj.optInt("active_7d", 0)));
                            statRegistrationsToday.setText(String.valueOf(obj.optInt("registrations_today", 0)));
                            statTotalMessages.setText(String.valueOf(obj.optInt("total_messages", 0)));
                            statPendingFlags.setText(String.valueOf(obj.optInt("pending_flags", 0)));
                            statUserCharacters.setText(String.valueOf(obj.optInt("total_user_characters", 0)));
                            statRegistrations7d.setText(String.valueOf(obj.optInt("registrations_7d", 0)));
                            statActive30d.setText(String.valueOf(obj.optInt("active_30d", 0)));
                        });
                    }
                }
            } catch (Exception e) {
                if (getActivity() != null) {
                    getActivity().runOnUiThread(() ->
                        Toast.makeText(getContext(), "Errore caricamento stats", Toast.LENGTH_SHORT).show());
                }
            }
        }).start();
    }
}
