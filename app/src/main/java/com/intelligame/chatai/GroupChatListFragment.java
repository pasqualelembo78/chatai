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
    private ExecutorService executor = Executors.newSingleThreadExecutor();
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
                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(baseUrl + "/characters", "GET", null, 10000);
                if (resp.statusCode == 200) {
                    JSONArray arr = new JSONArray(resp.body);
                    List<JSONObject> characters = new ArrayList<>();
                    for (int i = 0; i < arr.length(); i++) {
                        JSONObject c = arr.getJSONObject(i);
                        if (!c.optBoolean("is_adult", false)) {
                            characters.add(c);
                        }
                    }
                    mainHandler.post(() -> {
                        loadingBar.setVisibility(View.GONE);
                        showCreateDialogWithChars(characters);
                    });
                    return;
                }
            } catch (Exception ignored) {}
            mainHandler.post(() -> {
                loadingBar.setVisibility(View.GONE);
                Toast.makeText(getContext(), "Errore caricamento personaggi", Toast.LENGTH_SHORT).show();
            });
        });
    }

    private void showCreateDialogWithChars(List<JSONObject> characters) {
        LinearLayout container = new LinearLayout(getContext());
        container.setOrientation(LinearLayout.VERTICAL);
        int pad = (int) (48 * getResources().getDisplayMetrics().density);
        container.setPadding(pad, 32, pad, 0);

        EditText nameInput = new EditText(getContext());
        nameInput.setHint("Nome della chat di gruppo");
        container.addView(nameInput);

        TextView label = new TextView(getContext());
        label.setText("Seleziona i personaggi (min 2):");
        label.setPadding(0, 24, 0, 8);
        container.addView(label);

        ScrollView scroll = new ScrollView(getContext());
        LinearLayout checkList = new LinearLayout(getContext());
        checkList.setOrientation(LinearLayout.VERTICAL);
        CheckBox[] checkBoxes = new CheckBox[characters.size()];
        for (int i = 0; i < characters.size(); i++) {
            JSONObject c = characters.get(i);
            String name = c.optString("name", "?");
            String avatar = c.optString("avatar", "");
            checkBoxes[i] = new CheckBox(getContext());
            checkBoxes[i].setText(avatar + " " + name);
            checkBoxes[i].setTag(c.optString("id"));
            checkBoxes[i].setTextColor(Color.parseColor("#E0E0E0"));
            checkList.addView(checkBoxes[i]);
        }
        scroll.addView(checkList);
        container.addView(scroll);

        new AlertDialog.Builder(getContext())
            .setTitle("Nuova Chat di Gruppo")
            .setView(container)
            .setPositiveButton("Crea", (dialog, which) -> {
                String name = nameInput.getText().toString().trim();
                if (name.isEmpty()) {
                    Toast.makeText(getContext(), "Inserisci un nome", Toast.LENGTH_SHORT).show();
                    return;
                }
                List<String> selected = new ArrayList<>();
                for (CheckBox cb : checkBoxes) {
                    if (cb.isChecked()) {
                        selected.add((String) cb.getTag());
                    }
                }
                if (selected.size() < 2) {
                    Toast.makeText(getContext(), "Seleziona almeno 2 personaggi", Toast.LENGTH_SHORT).show();
                    return;
                }
                createGroupChat(name, selected);
            })
            .setNegativeButton("Annulla", null)
            .show();
    }

    private void createGroupChat(String name, List<String> characterIds) {
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
                    mainHandler.post(() -> {
                        Toast.makeText(getContext(), "Chat creata!", Toast.LENGTH_SHORT).show();
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
            executor = Executors.newSingleThreadExecutor();
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
