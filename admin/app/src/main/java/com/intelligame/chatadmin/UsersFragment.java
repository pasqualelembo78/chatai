package com.intelligame.chatadmin;

import android.app.AlertDialog;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ArrayAdapter;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.Fragment;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

public class UsersFragment extends Fragment {

    private AuthManager mAuth;
    private EditText searchInput;
    private RecyclerView usersList;
    private ProgressBar loadingBar;
    private UserAdapter adapter;
    private Handler searchHandler = new Handler(Looper.getMainLooper());
    private Runnable searchRunnable;

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater, @Nullable ViewGroup container, @Nullable Bundle savedInstanceState) {
        return inflater.inflate(R.layout.fragment_users, container, false);
    }

    @Override
    public void onViewCreated(@NonNull View view, @Nullable Bundle savedInstanceState) {
        super.onViewCreated(view, savedInstanceState);
        mAuth = ((ChatApplication) requireActivity().getApplication()).getAuthManager();

        searchInput = view.findViewById(R.id.search_input);
        usersList = view.findViewById(R.id.users_list);
        loadingBar = view.findViewById(R.id.loading_bar);

        usersList.setLayoutManager(new LinearLayoutManager(getContext()));
        adapter = new UserAdapter();
        usersList.setAdapter(adapter);

        view.findViewById(R.id.btn_create_user).setOnClickListener(v -> showCreateUserDialog());

        searchInput.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int start, int count, int after) {}
            @Override public void onTextChanged(CharSequence s, int start, int before, int count) {}
            @Override
            public void afterTextChanged(Editable s) {
                if (searchRunnable != null) searchHandler.removeCallbacks(searchRunnable);
                searchRunnable = () -> searchUsers(s.toString());
                searchHandler.postDelayed(searchRunnable, 400);
            }
        });

        loadUsers();
    }

    private void loadUsers() {
        loadingBar.setVisibility(View.VISIBLE);
        new Thread(() -> {
            try {
                String url = ((ChatApplication) requireActivity().getApplication()).getCurrentUrl() + "/admin/users";
                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(url, "GET", null, 10000);
                if (resp.statusCode == 200) {
                    JSONArray arr = new JSONArray(resp.body);
                    List<UserItem> users = new ArrayList<>();
                    for (int i = 0; i < arr.length(); i++) {
                        JSONObject obj = arr.getJSONObject(i);
                        users.add(parseUser(obj));
                    }
                    if (getActivity() != null) {
                        getActivity().runOnUiThread(() -> {
                            adapter.setUsers(users);
                            loadingBar.setVisibility(View.GONE);
                        });
                    }
                }
            } catch (Exception e) {
                if (getActivity() != null) {
                    getActivity().runOnUiThread(() -> {
                        loadingBar.setVisibility(View.GONE);
                        Toast.makeText(getContext(), "Errore caricamento utenti", Toast.LENGTH_SHORT).show();
                    });
                }
            }
        }).start();
    }

    private void searchUsers(String query) {
        if (query.isEmpty()) {
            loadUsers();
            return;
        }
        loadingBar.setVisibility(View.VISIBLE);
        new Thread(() -> {
            try {
                String url = ((ChatApplication) requireActivity().getApplication()).getCurrentUrl()
                        + "/admin/users/search?q=" + java.net.URLEncoder.encode(query, "UTF-8");
                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(url, "GET", null, 10000);
                if (resp.statusCode == 200) {
                    JSONArray arr = new JSONArray(resp.body);
                    List<UserItem> users = new ArrayList<>();
                    for (int i = 0; i < arr.length(); i++) {
                        JSONObject obj = arr.getJSONObject(i);
                        users.add(parseUser(obj));
                    }
                    if (getActivity() != null) {
                        getActivity().runOnUiThread(() -> {
                            adapter.setUsers(users);
                            loadingBar.setVisibility(View.GONE);
                        });
                    }
                }
            } catch (Exception e) {
                if (getActivity() != null) {
                    getActivity().runOnUiThread(() -> loadingBar.setVisibility(View.GONE));
                }
            }
        }).start();
    }

    private UserItem parseUser(JSONObject obj) {
        UserItem u = new UserItem();
        u.id = obj.optString("id", "");
        u.username = obj.optString("username", "");
        u.role = obj.optString("role", "user");
        u.email = obj.optString("email", "");
        u.bannedUntil = obj.optString("banned_until", null);
        u.createdAt = obj.optString("created_at", "");
        return u;
    }

    private void showCreateUserDialog() {
        LinearLayout layout = new LinearLayout(getContext());
        layout.setOrientation(LinearLayout.VERTICAL);
        int pad = (int)(48 * getResources().getDisplayMetrics().density);
        layout.setPadding(pad, 32, pad, 0);

        EditText usernameInput = new EditText(getContext());
        usernameInput.setHint("Username (3-20 caratteri)");
        usernameInput.setMinLines(1);
        layout.addView(usernameInput);

        EditText passwordInput = new EditText(getContext());
        passwordInput.setHint("Password (min 8 caratteri)");
        passwordInput.setMinLines(1);
        layout.addView(passwordInput);

        EditText emailInput = new EditText(getContext());
        emailInput.setHint("Email (opzionale)");
        emailInput.setMinLines(1);
        layout.addView(emailInput);

        TextView roleLabel = new TextView(getContext());
        roleLabel.setText("Ruolo:");
        roleLabel.setPadding(0, 24, 0, 8);
        layout.addView(roleLabel);

        Spinner roleSpinner = new Spinner(getContext());
        String[] roles = {"user", "moderator", "admin"};
        ArrayAdapter<String> spinnerAdapter = new ArrayAdapter<>(getContext(),
            android.R.layout.simple_spinner_dropdown_item, roles);
        roleSpinner.setAdapter(spinnerAdapter);
        layout.addView(roleSpinner);

        new AlertDialog.Builder(getContext())
            .setTitle("Crea Nuovo Utente")
            .setView(layout)
            .setPositiveButton("Crea", (dialog, which) -> {
                String username = usernameInput.getText().toString().trim();
                String password = passwordInput.getText().toString().trim();
                String email = emailInput.getText().toString().trim();
                String role = roles[roleSpinner.getSelectedItemPosition()];
                if (username.isEmpty() || password.isEmpty()) {
                    Toast.makeText(getContext(), "Username e password obbligatori", Toast.LENGTH_SHORT).show();
                    return;
                }
                createUser(username, password, email, role);
            })
            .setNegativeButton("Annulla", null)
            .show();
    }

    private void createUser(String username, String password, String email, String role) {
        loadingBar.setVisibility(View.VISIBLE);
        new Thread(() -> {
            try {
                String url = ((ChatApplication) requireActivity().getApplication()).getCurrentUrl() + "/admin/users";
                JSONObject body = new JSONObject();
                body.put("username", username);
                body.put("password", password);
                body.put("email", email);
                body.put("role", role);
                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(url, "POST", body.toString(), 10000);
                if (resp.statusCode == 200 || resp.statusCode == 201) {
                    if (getActivity() != null) {
                        getActivity().runOnUiThread(() -> {
                            Toast.makeText(getContext(), "Utente \"" + username + "\" creato", Toast.LENGTH_SHORT).show();
                            loadingBar.setVisibility(View.GONE);
                            loadUsers();
                        });
                    }
                } else {
                    String errMsg = "Errore: " + resp.statusCode;
                    try {
                        JSONObject err = new JSONObject(resp.body);
                        if (err.has("detail")) errMsg = err.getString("detail");
                    } catch (Exception ignored) {}
                    final String msg = errMsg;
                    if (getActivity() != null) {
                        getActivity().runOnUiThread(() -> {
                            Toast.makeText(getContext(), msg, Toast.LENGTH_LONG).show();
                            loadingBar.setVisibility(View.GONE);
                        });
                    }
                }
            } catch (Exception e) {
                if (getActivity() != null) {
                    getActivity().runOnUiThread(() -> {
                        Toast.makeText(getContext(), "Errore connessione", Toast.LENGTH_SHORT).show();
                        loadingBar.setVisibility(View.GONE);
                    });
                }
            }
        }).start();
    }

    class UserItem {
        String id, username, role, email, bannedUntil, createdAt;
    }

    class UserAdapter extends RecyclerView.Adapter<UserAdapter.VH> {
        private List<UserItem> users = new ArrayList<>();

        void setUsers(List<UserItem> list) {
            this.users = list;
            notifyDataSetChanged();
        }

        @NonNull
        @Override
        public VH onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
            View v = LayoutInflater.from(parent.getContext()).inflate(R.layout.item_user, parent, false);
            return new VH(v);
        }

        @Override
        public void onBindViewHolder(@NonNull VH holder, int position) {
            UserItem u = users.get(position);
            holder.username.setText(u.username);
            holder.email.setText(u.email.isEmpty() ? u.id : u.email);
            holder.created.setText("Creato: " + u.createdAt.substring(0, Math.min(10, u.createdAt.length())));

            holder.role.setText(u.role);
            int roleColor;
            switch (u.role) {
                case "admin": roleColor = Color.parseColor("#FF5252"); break;
                case "moderator": roleColor = Color.parseColor("#FFC107"); break;
                default: roleColor = Color.parseColor("#4CAF50"); break;
            }
            holder.role.setBackgroundColor(roleColor);
            holder.role.setTextColor(Color.WHITE);

            if (u.bannedUntil != null && !u.bannedUntil.equals("null") && !u.bannedUntil.isEmpty()) {
                holder.banStatus.setVisibility(View.VISIBLE);
                holder.banStatus.setText("BANNATO");
            } else {
                holder.banStatus.setVisibility(View.GONE);
            }

            holder.itemView.setOnClickListener(v -> {
                UserDetailFragment fragment = UserDetailFragment.newInstance(u.id);
                ((MainActivity) requireActivity()).loadFragment(fragment, "user_detail");
            });
        }

        @Override
        public int getItemCount() { return users.size(); }

        class VH extends RecyclerView.ViewHolder {
            TextView username, email, created, role, banStatus;
            VH(View v) {
                super(v);
                username = v.findViewById(R.id.user_username);
                email = v.findViewById(R.id.user_email);
                created = v.findViewById(R.id.user_created);
                role = v.findViewById(R.id.user_role);
                banStatus = v.findViewById(R.id.user_ban_status);
            }
        }
    }
}
