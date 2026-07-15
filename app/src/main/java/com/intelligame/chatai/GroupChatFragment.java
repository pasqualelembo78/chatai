package com.intelligame.chatai;

import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ProgressBar;
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

public class GroupChatFragment extends Fragment {

    private static final String ARG_CHAT_ID = "chat_id";
    private static final String ARG_CHAT_NAME = "chat_name";

    private int chatId;
    private String chatName;
    private AuthManager mAuth;
    private String baseUrl;
    private RecyclerView messagesList;
    private EditText messageInput;
    private Button btnSend;
    private ProgressBar loadingBar;
    private TextView titleView, subtitleView;
    private MessageAdapter adapter;
    private List<MessageItem> messages = new ArrayList<>();
    private ExecutorService executor = Executors.newSingleThreadExecutor();
    private Handler mainHandler = new Handler(Looper.getMainLooper());
    private boolean sending = false;

    private static final int[] CHARACTER_COLORS = {
        Color.parseColor("#4FC3F7"),
        Color.parseColor("#CE93D8"),
        Color.parseColor("#81C784"),
        Color.parseColor("#FFB74D"),
        Color.parseColor("#F06292"),
        Color.parseColor("#FF8A65"),
        Color.parseColor("#AED581"),
        Color.parseColor("#90A4AE"),
    };

    public static GroupChatFragment newInstance(int chatId, String chatName) {
        GroupChatFragment f = new GroupChatFragment();
        Bundle args = new Bundle();
        args.putInt(ARG_CHAT_ID, chatId);
        args.putString(ARG_CHAT_NAME, chatName);
        f.setArguments(args);
        return f;
    }

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater, @Nullable ViewGroup container, @Nullable Bundle savedInstanceState) {
        return inflater.inflate(R.layout.fragment_group_chat, container, false);
    }

    @Override
    public void onViewCreated(@NonNull View view, @Nullable Bundle savedInstanceState) {
        super.onViewCreated(view, savedInstanceState);
        chatId = getArguments() != null ? getArguments().getInt(ARG_CHAT_ID) : 0;
        chatName = getArguments() != null ? getArguments().getString(ARG_CHAT_NAME) : "";

        ChatApplication app = (ChatApplication) requireActivity().getApplication();
        mAuth = app.getAuthManager();
        baseUrl = app.getCurrentUrl();

        titleView = view.findViewById(R.id.group_title);
        subtitleView = view.findViewById(R.id.group_subtitle);
        messagesList = view.findViewById(R.id.messages_list);
        messageInput = view.findViewById(R.id.message_input);
        btnSend = view.findViewById(R.id.btn_send);
        loadingBar = view.findViewById(R.id.loading_bar);

        titleView.setText(chatName);
        subtitleView.setText("Caricamento...");

        LinearLayoutManager lm = new LinearLayoutManager(getContext());
        lm.setStackFromEnd(true);
        messagesList.setLayoutManager(lm);
        adapter = new MessageAdapter();
        messagesList.setAdapter(adapter);

        view.findViewById(R.id.btn_back).setOnClickListener(v ->
            ((MainActivity) requireActivity()).onBackPressed());

        view.findViewById(R.id.btn_group_settings).setOnClickListener(v -> showGroupSettings());

        btnSend.setOnClickListener(v -> sendMessage());

        loadMessages();
    }

    private void loadMessages() {
        executor.execute(() -> {
            try {
                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(
                    baseUrl + "/group-chats/" + chatId, "GET", null, 10000);
                if (resp.statusCode == 200) {
                    JSONObject obj = new JSONObject(resp.body);
                    JSONArray chars = obj.optJSONArray("character_ids");
                    int charCount = chars != null ? chars.length() : 0;
                    JSONArray msgs = obj.optJSONArray("messages");
                    List<MessageItem> items = new ArrayList<>();
                    if (msgs != null) {
                        for (int i = 0; i < msgs.length(); i++) {
                            JSONObject m = msgs.getJSONObject(i);
                            MessageItem item = new MessageItem();
                            item.senderType = m.optString("sender_type", "");
                            item.senderId = m.optString("sender_id", "");
                            item.role = m.optString("role", "");
                            item.content = m.optString("content", "");
                            item.timestamp = m.optString("timestamp", "");
                            item.senderName = resolveSenderName(m, charCount);
                            items.add(item);
                        }
                    }
                    final int cc = charCount;
                    mainHandler.post(() -> {
                        subtitleView.setText(cc + " personaggi");
                        messages.clear();
                        messages.addAll(items);
                        adapter.notifyDataSetChanged();
                        if (!messages.isEmpty()) {
                            messagesList.scrollToPosition(messages.size() - 1);
                        }
                    });
                }
            } catch (Exception e) {
                mainHandler.post(() ->
                    Toast.makeText(getContext(), "Errore caricamento", Toast.LENGTH_SHORT).show());
            }
        });
    }

    private String resolveSenderName(JSONObject msg, int charCount) {
        if ("user".equals(msg.optString("sender_type"))) {
            return "Tu";
        }
        String name = msg.optString("sender_id", "?");
        return name;
    }

    private void sendMessage() {
        String text = messageInput.getText().toString().trim();
        if (text.isEmpty() || sending) return;
        sending = true;
        messageInput.setText("");
        btnSend.setEnabled(false);

        MessageItem userMsg = new MessageItem();
        userMsg.senderType = "user";
        userMsg.senderId = "user";
        userMsg.role = "user";
        userMsg.content = text;
        userMsg.senderName = "Tu";
        userMsg.timestamp = "";
        messages.add(userMsg);
        adapter.notifyItemInserted(messages.size() - 1);
        messagesList.scrollToPosition(messages.size() - 1);

        loadingBar.setVisibility(View.VISIBLE);

        executor.execute(() -> {
            try {
                JSONObject body = new JSONObject();
                body.put("text", text);

                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(
                    baseUrl + "/group-chats/" + chatId + "/message",
                    "POST", body.toString(), 60000);

                if (resp.statusCode == 200) {
                    JSONObject result = new JSONObject(resp.body);
                    JSONArray responses = result.optJSONArray("responses");

                    if (responses != null) {
                        for (int i = 0; i < responses.length(); i++) {
                            JSONObject r = responses.getJSONObject(i);
                            MessageItem charMsg = new MessageItem();
                            charMsg.senderType = "character";
                            charMsg.senderId = r.optString("character_id", "");
                            charMsg.role = "assistant";
                            charMsg.content = r.optString("content", "");
                            charMsg.senderName = r.optString("character_name", "?");
                            charMsg.timestamp = "";
                            final int idx = i;
                            mainHandler.post(() -> {
                                messages.add(charMsg);
                                adapter.notifyItemInserted(messages.size() - 1);
                                messagesList.scrollToPosition(messages.size() - 1);
                            });
                            try { Thread.sleep(100); } catch (InterruptedException ignored) {}
                        }
                    }
                    mainHandler.post(() -> {
                        loadingBar.setVisibility(View.GONE);
                        sending = false;
                        btnSend.setEnabled(true);
                    });
                } else {
                    String errMsg = "Errore";
                    try {
                        JSONObject err = new JSONObject(resp.body);
                        if (err.has("detail")) errMsg = err.getString("detail");
                    } catch (Exception ignored) {}
                    final String msg = errMsg;
                    mainHandler.post(() -> {
                        Toast.makeText(getContext(), msg, Toast.LENGTH_SHORT).show();
                        loadingBar.setVisibility(View.GONE);
                        sending = false;
                        btnSend.setEnabled(true);
                        messageInput.setText(text);
                    });
                }
            } catch (Exception e) {
                mainHandler.post(() -> {
                    Toast.makeText(getContext(), "Errore connessione", Toast.LENGTH_SHORT).show();
                    loadingBar.setVisibility(View.GONE);
                    sending = false;
                    btnSend.setEnabled(true);
                    messageInput.setText(text);
                });
            }
        });
    }

    private void showGroupSettings() {
        loadingBar.setVisibility(View.VISIBLE);
        executor.execute(() -> {
            try {
                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(
                    baseUrl + "/group-chats/" + chatId, "GET", null, 10000);
                if (resp.statusCode == 200) {
                    JSONObject obj = new JSONObject(resp.body);
                    JSONArray currentChars = obj.optJSONArray("character_ids");
                    List<String> currentIds = new ArrayList<>();
                    if (currentChars != null) {
                        for (int i = 0; i < currentChars.length(); i++) {
                            currentIds.add(currentChars.getString(i));
                        }
                    }

                    AuthManager.HttpResponse allResp = mAuth.requestWithRefresh(
                        baseUrl + "/characters", "GET", null, 10000);
                    List<JSONObject> allChars = new ArrayList<>();
                    if (allResp.statusCode == 200) {
                        JSONArray arr = new JSONArray(allResp.body);
                        for (int i = 0; i < arr.length(); i++) {
                            JSONObject c = arr.getJSONObject(i);
                            if (!c.optBoolean("is_adult", false)) {
                                allChars.add(c);
                            }
                        }
                    }

                    final List<String> finalCurrentIds = currentIds;
                    final List<JSONObject> finalAllChars = allChars;
                    mainHandler.post(() -> {
                        loadingBar.setVisibility(View.GONE);
                        showManageCharactersDialog(finalCurrentIds, finalAllChars);
                    });
                }
            } catch (Exception e) {
                mainHandler.post(() -> {
                    loadingBar.setVisibility(View.GONE);
                    Toast.makeText(getContext(), "Errore caricamento", Toast.LENGTH_SHORT).show();
                });
            }
        });
    }

    private void showManageCharactersDialog(List<String> currentIds, List<JSONObject> allChars) {
        android.app.AlertDialog.Builder builder = new android.app.AlertDialog.Builder(getContext());
        builder.setTitle("Gestisci Personaggi");

        LinearLayout container = new LinearLayout(getContext());
        container.setOrientation(LinearLayout.VERTICAL);
        int pad = (int) (48 * getResources().getDisplayMetrics().density);
        container.setPadding(pad, 32, pad, 0);

        TextView currentLabel = new TextView(getContext());
        currentLabel.setText("Personaggi attuali (" + currentIds.size() + "):");
        currentLabel.setPadding(0, 0, 0, 8);
        currentLabel.setTextColor(Color.parseColor("#E0E0E0"));
        container.addView(currentLabel);

        for (String cid : currentIds) {
            String charName = cid;
            for (JSONObject c : allChars) {
                if (c.optString("id").equals(cid)) {
                    charName = c.optString("name", cid);
                    break;
                }
            }
            TextView charView = new TextView(getContext());
            charView.setText("✕ " + charName);
            charView.setPadding(0, 8, 0, 8);
            charView.setTextColor(Color.parseColor("#FF8A80"));
            charView.setTextSize(14);
            charView.setTag(cid);
            charView.setOnClickListener(v -> {
                removeCharacter(cid, charName);
            });
            container.addView(charView);
        }

        if (currentIds.size() < 8) {
            TextView addLabel = new TextView(getContext());
            addLabel.setText("\nAggiungi personaggio:");
            addLabel.setPadding(0, 16, 0, 8);
            addLabel.setTextColor(Color.parseColor("#E0E0E0"));
            container.addView(addLabel);

            for (JSONObject c : allChars) {
                String id = c.optString("id");
                if (!currentIds.contains(id)) {
                    String name = c.optString("name", "?");
                    String avatar = c.optString("avatar", "");
                    TextView addView = new TextView(getContext());
                    addView.setText("+ " + avatar + " " + name);
                    addView.setPadding(0, 8, 0, 8);
                    addView.setTextColor(Color.parseColor("#81C784"));
                    addView.setTextSize(14);
                    addView.setOnClickListener(v -> {
                        addCharacter(id, name);
                    });
                    container.addView(addView);
                }
            }
        }

        builder.setView(container);
        builder.setNegativeButton("Chiudi", null);
        builder.show();
    }

    private void addCharacter(String characterId, String characterName) {
        loadingBar.setVisibility(View.VISIBLE);
        executor.execute(() -> {
            try {
                JSONObject body = new JSONObject();
                body.put("character_id", characterId);
                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(
                    baseUrl + "/group-chats/" + chatId + "/characters",
                    "POST", body.toString(), 10000);
                mainHandler.post(() -> {
                    loadingBar.setVisibility(View.GONE);
                    if (resp.statusCode == 200 || resp.statusCode == 201) {
                        Toast.makeText(getContext(), characterName + " aggiunto!", Toast.LENGTH_SHORT).show();
                        loadMessages();
                    } else {
                        String errMsg = "Errore";
                        try {
                            JSONObject err = new JSONObject(resp.body);
                            if (err.has("detail")) errMsg = err.getString("detail");
                        } catch (Exception ignored) {}
                        Toast.makeText(getContext(), errMsg, Toast.LENGTH_SHORT).show();
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

    private void removeCharacter(String characterId, String characterName) {
        new android.app.AlertDialog.Builder(getContext())
            .setTitle("Rimuovi " + characterName + "?")
            .setMessage("Vuoi rimuovere " + characterName + " dalla chat?")
            .setPositiveButton("Rimuovi", (d, w) -> {
                loadingBar.setVisibility(View.VISIBLE);
                executor.execute(() -> {
                    try {
                        AuthManager.HttpResponse resp = mAuth.requestWithRefresh(
                            baseUrl + "/group-chats/" + chatId + "/characters/" + characterId,
                            "DELETE", null, 10000);
                        mainHandler.post(() -> {
                            loadingBar.setVisibility(View.GONE);
                            if (resp.statusCode == 200) {
                                Toast.makeText(getContext(), characterName + " rimosso", Toast.LENGTH_SHORT).show();
                                loadMessages();
                            } else {
                                String errMsg = "Errore";
                                try {
                                    JSONObject err = new JSONObject(resp.body);
                                    if (err.has("detail")) errMsg = err.getString("detail");
                                } catch (Exception ignored) {}
                                Toast.makeText(getContext(), errMsg, Toast.LENGTH_SHORT).show();
                            }
                        });
                    } catch (Exception e) {
                        mainHandler.post(() -> {
                            loadingBar.setVisibility(View.GONE);
                            Toast.makeText(getContext(), "Errore connessione", Toast.LENGTH_SHORT).show();
                        });
                    }
                });
            })
            .setNegativeButton("Annulla", null)
            .show();
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

    static class MessageItem {
        String senderType;
        String senderId;
        String role;
        String content;
        String timestamp;
        String senderName;
    }

    private class MessageAdapter extends RecyclerView.Adapter<MessageAdapter.VH> {
        private static final int VIEW_TYPE_USER = 0;
        private static final int VIEW_TYPE_CHARACTER = 1;

        @Override
        public int getItemViewType(int position) {
            return "user".equals(messages.get(position).senderType) ? VIEW_TYPE_USER : VIEW_TYPE_CHARACTER;
        }

        @NonNull
        @Override
        public VH onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
            TextView tv = new TextView(parent.getContext());
            int pad = (int) (12 * getResources().getDisplayMetrics().density);
            tv.setPadding(pad, pad, pad, pad);
            tv.setTextSize(14);
            tv.setLayoutParams(new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
            return new VH(tv);
        }

        @Override
        public void onBindViewHolder(@NonNull VH holder, int position) {
            MessageItem item = messages.get(position);
            TextView tv = (TextView) holder.itemView;

            if (VIEW_TYPE_USER == getItemViewType(position)) {
                tv.setText("Tu: " + item.content);
                tv.setTextColor(Color.parseColor("#E0E0E0"));
                tv.setBackgroundColor(Color.parseColor("#2A2A4A"));
            } else {
                int colorIndex = Math.abs(item.senderId.hashCode()) % CHARACTER_COLORS.length;
                int color = CHARACTER_COLORS[colorIndex];
                tv.setText(item.senderName + ": " + item.content);
                tv.setTextColor(color);
                tv.setBackgroundColor(Color.parseColor("#1A1A2E"));
            }
        }

        @Override
        public int getItemCount() { return messages.size(); }

        class VH extends RecyclerView.ViewHolder {
            VH(View itemView) { super(itemView); }
        }
    }
}
