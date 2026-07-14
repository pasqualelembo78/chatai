package com.intelligame.chatai;

import android.graphics.Color;
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

public class UserDetailFragment extends Fragment {

    private static final String ARG_USER_ID = "user_id";
    private AuthManager mAuth;
    private String userId;

    public static UserDetailFragment newInstance(String userId) {
        UserDetailFragment f = new UserDetailFragment();
        Bundle args = new Bundle();
        args.putString(ARG_USER_ID, userId);
        f.setArguments(args);
        return f;
    }

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater, @Nullable ViewGroup container, @Nullable Bundle savedInstanceState) {
        return inflater.inflate(R.layout.fragment_user_detail, container, false);
    }

    @Override
    public void onViewCreated(@NonNull View view, @Nullable Bundle savedInstanceState) {
        super.onViewCreated(view, savedInstanceState);
        mAuth = ((ChatApplication) requireActivity().getApplication()).getAuthManager();
        userId = getArguments() != null ? getArguments().getString(ARG_USER_ID) : "";

        view.findViewById(R.id.btn_back).setOnClickListener(v ->
            ((MainActivity) requireActivity()).onBackPressed());

        view.findViewById(R.id.btn_role_user).setOnClickListener(v -> updateRole("user"));
        view.findViewById(R.id.btn_role_moderator).setOnClickListener(v -> updateRole("moderator"));
        view.findViewById(R.id.btn_role_admin).setOnClickListener(v -> updateRole("admin"));

        view.findViewById(R.id.btn_ban_24h).setOnClickListener(v -> banUser(24));
        view.findViewById(R.id.btn_ban_72h).setOnClickListener(v -> banUser(72));
        view.findViewById(R.id.btn_unban).setOnClickListener(v -> banUser(0));

        loadUserDetail();
    }

    private void loadUserDetail() {
        new Thread(() -> {
            try {
                String url = ((ChatApplication) requireActivity().getApplication()).getCurrentUrl()
                        + "/admin/users/" + userId;
                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(url, "GET", null, 10000);
                if (resp.statusCode == 200) {
                    JSONObject obj = new JSONObject(resp.body);
                    if (getActivity() != null) {
                        getActivity().runOnUiThread(() -> {
                            ((TextView) getView().findViewById(R.id.detail_username))
                                .setText(obj.optString("username", ""));
                            ((TextView) getView().findViewById(R.id.detail_email))
                                .setText(obj.optString("email", "Nessuna email"));
                            ((TextView) getView().findViewById(R.id.detail_id))
                                .setText("ID: " + obj.optString("id", ""));

                            String role = obj.optString("role", "user");
                            TextView roleView = getView().findViewById(R.id.detail_role);
                            roleView.setText("Ruolo: " + role);
                            int roleColor;
                            switch (role) {
                                case "admin": roleColor = Color.parseColor("#FF5252"); break;
                                case "moderator": roleColor = Color.parseColor("#FFC107"); break;
                                default: roleColor = Color.parseColor("#4CAF50"); break;
                            }
                            roleView.setTextColor(roleColor);

                            String bannedUntil = obj.optString("banned_until", "null");
                            TextView banView = getView().findViewById(R.id.detail_ban);
                            if (bannedUntil != null && !bannedUntil.equals("null") && !bannedUntil.isEmpty()) {
                                banView.setVisibility(View.VISIBLE);
                                banView.setText("BANNATO fino a: " + bannedUntil);
                            } else {
                                banView.setVisibility(View.GONE);
                            }

                            String created = obj.optString("created_at", "");
                            ((TextView) getView().findViewById(R.id.detail_created))
                                .setText("Creato: " + (created.length() > 10 ? created.substring(0, 16) : created));

                            String lastLogin = obj.optString("last_login", "null");
                            ((TextView) getView().findViewById(R.id.detail_last_login))
                                .setText("Ultimo accesso: " + (lastLogin.equals("null") ? "Mai" : (lastLogin.length() > 10 ? lastLogin.substring(0, 16) : lastLogin)));

                            ((TextView) getView().findViewById(R.id.detail_messages))
                                .setText("Messaggi: " + obj.optInt("message_count", 0));
                            ((TextView) getView().findViewById(R.id.detail_conversations))
                                .setText("Conversazioni: " + obj.optInt("conversation_count", 0));
                            ((TextView) getView().findViewById(R.id.detail_mevacoins))
                                .setText("Mevacoins: " + obj.optInt("mevacoins", 0));
                        });
                    }
                }
            } catch (Exception e) {
                if (getActivity() != null) {
                    getActivity().runOnUiThread(() ->
                        Toast.makeText(getContext(), "Errore caricamento dettagli", Toast.LENGTH_SHORT).show());
                }
            }
        }).start();
    }

    private void updateRole(String role) {
        new Thread(() -> {
            try {
                String url = ((ChatApplication) requireActivity().getApplication()).getCurrentUrl()
                        + "/admin/users/" + userId + "/role";
                JSONObject body = new JSONObject();
                body.put("role", role);
                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(url, "PUT", body.toString(), 10000);
                if (resp.statusCode == 200) {
                    if (getActivity() != null) {
                        getActivity().runOnUiThread(() -> {
                            Toast.makeText(getContext(), "Ruolo aggiornato", Toast.LENGTH_SHORT).show();
                            loadUserDetail();
                        });
                    }
                }
            } catch (Exception e) {
                if (getActivity() != null) {
                    getActivity().runOnUiThread(() ->
                        Toast.makeText(getContext(), "Errore aggiornamento ruolo", Toast.LENGTH_SHORT).show());
                }
            }
        }).start();
    }

    private void banUser(int hours) {
        new Thread(() -> {
            try {
                String url = ((ChatApplication) requireActivity().getApplication()).getCurrentUrl() + "/admin/ban";
                JSONObject body = new JSONObject();
                body.put("user_id", userId);
                body.put("hours", hours);
                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(url, "POST", body.toString(), 10000);
                if (resp.statusCode == 200) {
                    if (getActivity() != null) {
                        getActivity().runOnUiThread(() -> {
                            String msg = hours > 0 ? "Utente bannato per " + hours + "h" : "Utente sbannato";
                            Toast.makeText(getContext(), msg, Toast.LENGTH_SHORT).show();
                            loadUserDetail();
                        });
                    }
                }
            } catch (Exception e) {
                if (getActivity() != null) {
                    getActivity().runOnUiThread(() ->
                        Toast.makeText(getContext(), "Errore ban", Toast.LENGTH_SHORT).show());
                }
            }
        }).start();
    }
}
