package com.intelligame.chatai;

import android.app.AlertDialog;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ArrayAdapter;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
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
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class GroupChatListFragment extends Fragment {

    private RecyclerView groupChatList;
    private TextView emptyText;
    private ProgressBar loadingBar;
    private ExecutorService executor = new SafeExecutor();
    private Handler mainHandler = new Handler(Looper.getMainLooper());
    private AuthManager mAuth;
    private String baseUrl;
    private GroupChatAdapter adapter;

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater, @Nullable ViewGroup container, @Nullable Bundle savedInstanceState) {
        return inflater.inflate(R.layout.fragment_group_chat_list, container, false);
    }

    @Override
    public void onViewCreated(@NonNull View view, @Nullable Bundle savedInstanceState) {
        super.onViewCreated(view, savedInstanceState);
        ChatApplication app = (ChatApplication) requireActivity().getApplication();
        mAuth = app.getAuthManager();
        baseUrl = app.getCurrentUrl();

        groupChatList = view.findViewById(R.id.group_chat_list);
        emptyText = view.findViewById(R.id.empty_text);
        loadingBar = view.findViewById(R.id.loading_bar);

        groupChatList.setLayoutManager(new LinearLayoutManager(getContext()));
        adapter = new GroupChatAdapter();
        groupChatList.setAdapter(adapter);

        view.findViewById(R.id.btn_create_group).setOnClickListener(v -> showCreateDialog());

        loadGroupChats();
        loadInvitations();
    }

    private void loadInvitations() {
        executor.execute(() -> {
            try {
                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(baseUrl + "/user/invitations", "GET", null, 5000);
                if (resp.statusCode == 200) {
                    JSONArray arr = new JSONArray(resp.body);
                    if (arr.length() > 0) {
                        StringBuilder msg = new StringBuilder();
                        msg.append("Hai ").append(arr.length()).append(" invito/i in attesa:");
                        for (int i = 0; i < arr.length(); i++) {
                            JSONObject inv = arr.getJSONObject(i);
                            msg.append("\n- ").append(inv.optString("chat_name"))
                               .append(" da ").append(inv.optString("inviter_id"));
                        }
                        mainHandler.post(() -> {
                            new android.app.AlertDialog.Builder(getContext())
                                .setTitle("Inviti in attesa")
                                .setMessage(msg.toString())
                                .setPositiveButton("Vedi", (d, w) -> showInvitationsDialog())
                                .setNegativeButton("Più tardi", null)
                                .show();
                        });
                    }
                }
            } catch (Exception ignored) {}
        });
    }

    private void showInvitationsDialog() {
        loadingBar.setVisibility(View.VISIBLE);
        executor.execute(() -> {
            try {
                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(baseUrl + "/user/invitations", "GET", null, 5000);
                if (resp.statusCode == 200) {
                    JSONArray arr = new JSONArray(resp.body);
                    List<JSONObject> invitations = new ArrayList<>();
                    for (int i = 0; i < arr.length(); i++) {
                        invitations.add(arr.getJSONObject(i));
                    }
                    mainHandler.post(() -> {
                        loadingBar.setVisibility(View.GONE);
                        if (invitations.isEmpty()) {
                            Toast.makeText(getContext(), "Nessun invito in sospeso", Toast.LENGTH_SHORT).show();
                            return;
                        }
                        for (JSONObject inv : invitations) {
                            showSingleInvitation(inv);
                        }
                    });
                }
            } catch (Exception e) {
                mainHandler.post(() -> loadingBar.setVisibility(View.GONE));
            }
        });
    }

    private void showSingleInvitation(JSONObject inv) {
        int invId = inv.optInt("id");
        String chatName = inv.optString("chat_name", "Chat");
        String inviter = inv.optString("inviter_id", "Sconosciuto");

        new android.app.AlertDialog.Builder(getContext())
            .setTitle("Invito a: " + chatName)
            .setMessage(inviter + " ti ha invitato a una chat di gruppo.")
            .setPositiveButton("Accetta", (d, w) -> respondToInvitation(invId, true))
            .setNegativeButton("Rifiuta", (d, w) -> respondToInvitation(invId, false))
            .setCancelable(false)
            .show();
    }

    private void respondToInvitation(int invitationId, boolean accept) {
        loadingBar.setVisibility(View.VISIBLE);
        executor.execute(() -> {
            try {
                JSONObject body = new JSONObject();
                body.put("accept", accept);
                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(
                    baseUrl + "/user/invitations/" + invitationId + "/respond",
                    "POST", body.toString(), 5000);
                mainHandler.post(() -> {
                    loadingBar.setVisibility(View.GONE);
                    if (resp.statusCode == 200) {
                        String action = accept ? "Accettato" : "Rifiutato";
                        Toast.makeText(getContext(), action + "!", Toast.LENGTH_SHORT).show();
                        loadGroupChats();
                    } else {
                        Toast.makeText(getContext(), "Errore", Toast.LENGTH_SHORT).show();
                    }
                });
            } catch (Exception e) {
                mainHandler.post(() -> {
                    loadingBar.setVisibility(View.GONE);
                    Toast.makeText(getContext(), "Errore connessione", Toast.LENGTH_SHORT).show();
                });
            }
        });
    }

    private void loadGroupChats() {
        loadingBar.setVisibility(View.VISIBLE);
        executor.execute(() -> {
            try {
                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(baseUrl + "/group-chats", "GET", null, 10000);
                if (resp.statusCode == 200) {
                    JSONArray arr = new JSONArray(resp.body);
                    List<GroupChatItem> items = new ArrayList<>();
                    for (int i = 0; i < arr.length(); i++) {
                        JSONObject obj = arr.getJSONObject(i);
                        GroupChatItem item = new GroupChatItem();
                        item.id = obj.optInt("id");
                        item.name = obj.optString("name", "");
                        item.createdAt = obj.optString("created_at", "");
                        item.messageCount = obj.optInt("message_count", 0);
                        JSONArray chars = obj.optJSONArray("character_ids");
                        item.characterIds = new ArrayList<>();
                        if (chars != null) {
                            for (int j = 0; j < chars.length(); j++) {
                                item.characterIds.add(chars.getString(j));
                            }
                        }
                        items.add(item);
                    }
                    mainHandler.post(() -> {
                        loadingBar.setVisibility(View.GONE);
                        if (items.isEmpty()) {
                            groupChatList.setVisibility(View.GONE);
                            emptyText.setVisibility(View.VISIBLE);
                        } else {
                            groupChatList.setVisibility(View.VISIBLE);
                            emptyText.setVisibility(View.GONE);
                            adapter.setData(items);
                        }
                    });
                } else {
                    mainHandler.post(() -> loadingBar.setVisibility(View.GONE));
                }
            } catch (Exception e) {
                mainHandler.post(() -> {
                    loadingBar.setVisibility(View.GONE);
                    Toast.makeText(getContext(), "Errore caricamento", Toast.LENGTH_SHORT).show();
                });
            }
        });
    }

    private void showCreateDialog() {
        loadingBar.setVisibility(View.VISIBLE);
        executor.execute(() -> {
            try {
                AuthManager.HttpResponse charResp = mAuth.requestWithRefresh(baseUrl + "/characters", "GET", null, 10000);
                List<JSONObject> characters = new ArrayList<>();
                if (charResp.statusCode == 200) {
                    JSONArray arr = new JSONArray(charResp.body);
                    for (int i = 0; i < arr.length(); i++) {
                        JSONObject c = arr.getJSONObject(i);
                        if (!c.optBoolean("is_adult", false)) {
                            characters.add(c);
                        }
                    }
                }

                AuthManager.HttpResponse userResp = mAuth.requestWithRefresh(baseUrl + "/users/search?q=", "GET", null, 5000);
                List<JSONObject> users = new ArrayList<>();
                if (userResp.statusCode == 200) {
                    JSONArray arr = new JSONArray(userResp.body);
                    for (int i = 0; i < arr.length(); i++) {
                        users.add(arr.getJSONObject(i));
                    }
                }

                final List<JSONObject> finalChars = characters;
                final List<JSONObject> finalUsers = users;
                mainHandler.post(() -> {
                    loadingBar.setVisibility(View.GONE);
                    showCreateDialogFull(finalChars, finalUsers);
                });
                return;
            } catch (Exception ignored) {}
            mainHandler.post(() -> {
                loadingBar.setVisibility(View.GONE);
                Toast.makeText(getContext(), "Errore caricamento", Toast.LENGTH_SHORT).show();
            });
        });
    }

    private void showCreateDialogFull(List<JSONObject> characters, List<JSONObject> users) {
        LinearLayout container = new LinearLayout(getContext());
        container.setOrientation(LinearLayout.VERTICAL);
        int pad = (int) (48 * getResources().getDisplayMetrics().density);
        container.setPadding(pad, 32, pad, 0);

        EditText nameInput = new EditText(getContext());
        nameInput.setHint("Nome della chat di gruppo");
        container.addView(nameInput);

        TextView charLabel = new TextView(getContext());
        charLabel.setText("Personaggi (min 2):");
        charLabel.setPadding(0, 24, 0, 8);
        charLabel.setTextColor(Color.parseColor("#E0E0E0"));
        container.addView(charLabel);

        CheckBox[] charBoxes = new CheckBox[characters.size()];
        for (int i = 0; i < characters.size(); i++) {
            JSONObject c = characters.get(i);
            String name = c.optString("name", "?");
            String avatar = c.optString("avatar", "");
            charBoxes[i] = new CheckBox(getContext());
            charBoxes[i].setText(avatar + " " + name);
            charBoxes[i].setTag(c.optString("id"));
            charBoxes[i].setTextColor(Color.parseColor("#E0E0E0"));
            container.addView(charBoxes[i]);
        }

        TextView userLabel = new TextView(getContext());
        userLabel.setText("\nPersone da invitare:");
        userLabel.setPadding(0, 24, 0, 8);
        userLabel.setTextColor(Color.parseColor("#E0E0E0"));
        container.addView(userLabel);

        EditText userSearch = new EditText(getContext());
        userSearch.setHint("Cerca username...");
        userSearch.setTextColor(Color.parseColor("#E0E0E0"));
        userSearch.setTextSize(14);
        container.addView(userSearch);

        LinearLayout userList = new LinearLayout(getContext());
        userList.setOrientation(LinearLayout.VERTICAL);
        container.addView(userList);

        List<String> selectedUserIds = new ArrayList<>();
        List<TextView> userResultViews = new ArrayList<>();

        userSearch.setOnEditorActionListener((v, actionId, event) -> {
            String query = userSearch.getText().toString().trim();
            if (!query.isEmpty()) {
                searchUsersForCreate(query, userList, userResultViews, selectedUserIds);
            }
            return true;
        });

        TextView selectedLabel = new TextView(getContext());
        selectedLabel.setText("\nUtenti selezionati: 0");
        selectedLabel.setPadding(0, 16, 0, 4);
        selectedLabel.setTextColor(Color.parseColor("#81C784"));
        selectedLabel.setTag("selected_label");
        container.addView(selectedLabel);

        for (JSONObject u : users) {
            String uid = u.optString("id");
            String username = u.optString("username", uid);
            TextView userView = new TextView(getContext());
            userView.setText("+ " + username);
            userView.setPadding(0, 8, 0, 8);
            userView.setTextColor(Color.parseColor("#4FC3F7"));
            userView.setTextSize(14);
            userView.setOnClickListener(v -> {
                if (!selectedUserIds.contains(uid)) {
                    selectedUserIds.add(uid);
                    userView.setTextColor(Color.parseColor("#81C784"));
                    userView.setText("✓ " + username);
                    selectedLabel.setText("Utenti selezionati: " + selectedUserIds.size());
                } else {
                    selectedUserIds.remove(uid);
                    userView.setTextColor(Color.parseColor("#4FC3F7"));
                    userView.setText("+ " + username);
                    selectedLabel.setText("Utenti selezionati: " + selectedUserIds.size());
                }
            });
            container.addView(userView);
        }

        ScrollView scroll = new ScrollView(getContext());
        scroll.addView(container);

        new AlertDialog.Builder(getContext())
            .setTitle("Nuova Chat di Gruppo")
            .setView(scroll)
            .setPositiveButton("Crea", (dialog, which) -> {
                String name = nameInput.getText().toString().trim();
                if (name.isEmpty()) {
                    Toast.makeText(getContext(), "Inserisci un nome", Toast.LENGTH_SHORT).show();
                    return;
                }
                List<String> selectedChars = new ArrayList<>();
                for (CheckBox cb : charBoxes) {
                    if (cb.isChecked()) {
                        selectedChars.add((String) cb.getTag());
                    }
                }
                if (selectedChars.size() < 2) {
                    Toast.makeText(getContext(), "Seleziona almeno 2 personaggi", Toast.LENGTH_SHORT).show();
                    return;
                }
                createGroupChat(name, selectedChars, selectedUserIds);
            })
            .setNegativeButton("Annulla", null)
            .show();
    }

    private void searchUsersForCreate(String query, LinearLayout userList, List<TextView> resultViews, List<String> selectedUserIds) {
        executor.execute(() -> {
            try {
                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(
                    baseUrl + "/users/search?q=" + query, "GET", null, 5000);
                if (resp.statusCode == 200) {
                    JSONArray arr = new JSONArray(resp.body);
                    List<JSONObject> results = new ArrayList<>();
                    for (int i = 0; i < arr.length(); i++) {
                        results.add(arr.getJSONObject(i));
                    }
                    mainHandler.post(() -> {
                        userList.removeAllViews();
                        resultViews.clear();
                        if (results.isEmpty()) {
                            TextView noResult = new TextView(getContext());
                            noResult.setText("Nessun risultato");
                            noResult.setTextColor(Color.parseColor("#888888"));
                            userList.addView(noResult);
                            return;
                        }
                        for (JSONObject u : results) {
                            String uid = u.optString("id");
                            String username = u.optString("username", uid);
                            TextView userView = new TextView(getContext());
                            boolean alreadySelected = selectedUserIds.contains(uid);
                            userView.setText(alreadySelected ? "✓ " + username : "+ " + username);
                            userView.setTextColor(Color.parseColor(alreadySelected ? "#81C784" : "#4FC3F7"));
                            userView.setPadding(0, 8, 0, 8);
                            userView.setTextSize(14);
                            userView.setOnClickListener(v -> {
                                if (!selectedUserIds.contains(uid)) {
                                    selectedUserIds.add(uid);
                                    userView.setTextColor(Color.parseColor("#81C784"));
                                    userView.setText("✓ " + username);
                                } else {
                                    selectedUserIds.remove(uid);
                                    userView.setTextColor(Color.parseColor("#4FC3F7"));
                                    userView.setText("+ " + username);
                                }
                            });
                            userList.addView(userView);
                            resultViews.add(userView);
                        }
                    });
                }
            } catch (Exception e) {
                mainHandler.post(() -> {
                    userList.removeAllViews();
                    TextView errView = new TextView(getContext());
                    errView.setText("Errore ricerca");
                    errView.setTextColor(Color.parseColor("#FF8A80"));
                    userList.addView(errView);
                });
            }
        });
    }

    private void createGroupChat(String name, List<String> characterIds, List<String> userIds) {
        loadingBar.setVisibility(View.VISIBLE);
        executor.execute(() -> {
            try {
                JSONObject body = new JSONObject();
                body.put("name", name);
                JSONArray ids = new JSONArray();
                for (String id : characterIds) ids.put(id);
                body.put("character_ids", ids);

                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(
                    baseUrl + "/group-chats", "POST", body.toString(), 10000);
                if (resp.statusCode == 200 || resp.statusCode == 201) {
                    JSONObject result = new JSONObject(resp.body);
                    int chatId = result.optInt("id", 0);

                    int invited = 0;
                    for (String uid : userIds) {
                        try {
                            JSONObject partBody = new JSONObject();
                            partBody.put("user_id", uid);
                            AuthManager.HttpResponse partResp = mAuth.requestWithRefresh(
                                baseUrl + "/group-chats/" + chatId + "/participants",
                                "POST", partBody.toString(), 5000);
                            if (partResp.statusCode == 200 || partResp.statusCode == 201) {
                                invited++;
                            }
                        } catch (Exception ignored) {}
                    }

                    final int finalInvited = invited;
                    mainHandler.post(() -> {
                        String msg = "Chat creata!";
                        if (finalInvited > 0) {
                            msg += " " + finalInvited + " invito/i inviati.";
                        }
                        Toast.makeText(getContext(), msg, Toast.LENGTH_SHORT).show();
                        loadGroupChats();
                    });
                } else {
                    String errMsg = "Errore";
                    try {
                        JSONObject err = new JSONObject(resp.body);
                        if (err.has("detail")) errMsg = err.getString("detail");
                    } catch (Exception ignored) {}
                    final String msg = errMsg;
                    mainHandler.post(() -> {
                        Toast.makeText(getContext(), msg, Toast.LENGTH_LONG).show();
                        loadingBar.setVisibility(View.GONE);
                    });
                }
            } catch (Exception e) {
                mainHandler.post(() -> {
                    Toast.makeText(getContext(), "Errore connessione", Toast.LENGTH_SHORT).show();
                    loadingBar.setVisibility(View.GONE);
                });
            }
        });
    }

    @Override
    public void onStart() {
        super.onStart();
        if (executor == null || executor.isShutdown()) {
            executor = new SafeExecutor();
        }
    }

    @Override
    public void onStop() {
        super.onStop();
    }

    static class GroupChatItem {
        int id;
        String name;
        String createdAt;
        int messageCount;
        List<String> characterIds;
    }

    private class GroupChatAdapter extends RecyclerView.Adapter<GroupChatAdapter.VH> {
        private List<GroupChatItem> data = new ArrayList<>();

        void setData(List<GroupChatItem> items) {
            data = items;
            notifyDataSetChanged();
        }

        @NonNull
        @Override
        public VH onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
            View v = LayoutInflater.from(parent.getContext()).inflate(R.layout.item_group_chat, parent, false);
            return new VH(v);
        }

        @Override
        public void onBindViewHolder(@NonNull VH holder, int position) {
            GroupChatItem item = data.get(position);
            holder.name.setText("👥 " + item.name);
            holder.msgCount.setText(item.messageCount + " msg");
            String created = item.createdAt.length() > 10 ? item.createdAt.substring(0, 10) : item.createdAt;
            holder.created.setText("Creata: " + created);
            holder.characters.setText(item.characterIds.size() + " personaggi");

            holder.itemView.setOnClickListener(v -> {
                if (getActivity() instanceof MainActivity) {
                    ((MainActivity) getActivity()).openGroupChat(item.id, item.name);
                }
            });

            holder.itemView.setOnLongClickListener(v -> {
                new AlertDialog.Builder(getContext())
                    .setTitle("Elimina chat di gruppo")
                    .setMessage("Eliminare \"" + item.name + "\"?")
                    .setPositiveButton("Elimina", (d, w) -> deleteGroupChat(item.id))
                    .setNegativeButton("Annulla", null)
                    .show();
                return true;
            });
        }

        @Override
        public int getItemCount() { return data.size(); }

        class VH extends RecyclerView.ViewHolder {
            TextView name, msgCount, created, characters;
            VH(View v) {
                super(v);
                name = v.findViewById(R.id.group_name);
                msgCount = v.findViewById(R.id.group_msg_count);
                created = v.findViewById(R.id.group_created);
                characters = v.findViewById(R.id.group_characters);
            }
        }
    }

    private void deleteGroupChat(int chatId) {
        executor.execute(() -> {
            try {
                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(
                    baseUrl + "/group-chats/" + chatId, "DELETE", null, 10000);
                if (resp.statusCode == 200) {
                    mainHandler.post(() -> {
                        Toast.makeText(getContext(), "Chat eliminata", Toast.LENGTH_SHORT).show();
                        loadGroupChats();
                    });
                }
            } catch (Exception ignored) {}
        });
    }
}
