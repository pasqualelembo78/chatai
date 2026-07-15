package com.intelligame.chatai;

import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageButton;
import android.widget.LinearLayout;
import android.widget.PopupMenu;
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
import java.util.HashMap;
import java.util.List;
import java.util.Map;
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
    private Map<String, String> charIdToName = new HashMap<>();
    private Map<String, String> userIdToName = new HashMap<>();
    private ExecutorService executor = Executors.newSingleThreadExecutor();
    private Handler mainHandler = new Handler(Looper.getMainLooper());
    private volatile boolean sending = false;
    private volatile boolean isCancelled = false;

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

        ImageButton copyButton = view.findViewById(R.id.copy_button);
        copyButton.setOnClickListener(v -> copyChatToClipboard());

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

                    Map<String, String> idToName = new HashMap<>();
                    AuthManager.HttpResponse allResp = mAuth.requestWithRefresh(
                        baseUrl + "/characters", "GET", null, 10000);
                    if (allResp.statusCode == 200) {
                        JSONArray allChars = new JSONArray(allResp.body);
                        for (int i = 0; i < allChars.length(); i++) {
                            JSONObject c = allChars.getJSONObject(i);
                            idToName.put(c.optString("id"), c.optString("name", ""));
                        }
                    }

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
                            item.senderName = resolveSenderName(item, idToName);
                            items.add(item);
                        }
                    }
                    final int cc = charCount;
                    final Map<String, String> finalIdToName = idToName;
                    mainHandler.post(() -> {
                        charIdToName.putAll(finalIdToName);
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

    private String resolveSenderName(MessageItem item, Map<String, String> idToName) {
        if ("user".equals(item.senderType)) {
            String myId = mAuth.getUserId();
            if (item.senderId.equals(myId)) {
                return "Tu";
            }
            String name = userIdToName.get(item.senderId);
            if (name != null) return name;
            return item.senderId.length() > 8 ? item.senderId.substring(0, 8) + "..." : item.senderId;
        }
        String name = idToName.get(item.senderId);
        return name != null ? name : item.senderId;
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
                    "POST", body.toString(), 180000);

                if (resp.statusCode == 200) {
                    JSONObject result = new JSONObject(resp.body);
                    JSONArray responses = result.optJSONArray("responses");

                    if (responses != null) {
                        for (int i = 0; i < responses.length(); i++) {
                            if (isCancelled) break;
                            JSONObject r = responses.getJSONObject(i);
                            MessageItem charMsg = new MessageItem();
                            charMsg.senderType = "character";
                            charMsg.senderId = r.optString("character_id", "");
                            charMsg.role = "assistant";
                            charMsg.content = r.optString("content", "");
                            charMsg.senderName = r.optString("character_name", "?");
                            charMsg.timestamp = "";
                            final int idx = i;
                            mainHandler.postDelayed(() -> {
                                if (!isCancelled && isAdded()) {
                                    messages.add(charMsg);
                                    adapter.notifyItemInserted(messages.size() - 1);
                                    messagesList.scrollToPosition(messages.size() - 1);
                                }
                            }, (i + 1) * 150L);
                        }
                    }
                    if (!isCancelled) {
                        mainHandler.post(() -> {
                            if (isAdded()) {
                                loadingBar.setVisibility(View.GONE);
                                sending = false;
                                btnSend.setEnabled(true);
                            }
                        });
                    }
                } else {
                    if (isCancelled) return;
                    String errMsg = "Errore";
                    try {
                        JSONObject err = new JSONObject(resp.body);
                        if (err.has("detail")) errMsg = err.getString("detail");
                    } catch (Exception ignored) {}
                    final String msg = errMsg;
                    mainHandler.post(() -> {
                        if (isAdded()) {
                            Toast.makeText(getContext(), msg, Toast.LENGTH_SHORT).show();
                            loadingBar.setVisibility(View.GONE);
                            sending = false;
                            btnSend.setEnabled(true);
                            messageInput.setText(text);
                        }
                    });
                }
            } catch (Exception e) {
                if (isCancelled) return;
                mainHandler.post(() -> {
                    if (isAdded()) {
                        Toast.makeText(getContext(), "Errore connessione", Toast.LENGTH_SHORT).show();
                        loadingBar.setVisibility(View.GONE);
                        sending = false;
                        btnSend.setEnabled(true);
                        messageInput.setText(text);
                    }
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
                    JSONArray participantsArr = obj.optJSONArray("participants");
                    List<String> participantIds = new ArrayList<>();
                    if (participantsArr != null) {
                        for (int i = 0; i < participantsArr.length(); i++) {
                            participantIds.add(participantsArr.getString(i));
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

                    Map<String, String> uidToName = new HashMap<>();
                    for (String pid : participantIds) {
                        try {
                            AuthManager.HttpResponse userResp = mAuth.requestWithRefresh(
                                baseUrl + "/users/search?q=" + pid, "GET", null, 3000);
                            if (userResp.statusCode == 200) {
                                JSONArray uarr = new JSONArray(userResp.body);
                                for (int i = 0; i < uarr.length(); i++) {
                                    JSONObject u = uarr.getJSONObject(i);
                                    if (pid.equals(u.optString("id"))) {
                                        uidToName.put(pid, u.optString("username", pid));
                                        break;
                                    }
                                }
                            }
                        } catch (Exception ignored) {}
                    }

                    final List<String> finalCurrentIds = currentIds;
                    final List<JSONObject> finalAllChars = allChars;
                    final List<String> finalParticipantIds = participantIds;
                    final Map<String, String> finalUidToName = uidToName;
                    mainHandler.post(() -> {
                        loadingBar.setVisibility(View.GONE);
                        userIdToName.putAll(finalUidToName);
                        showManageDialog(finalCurrentIds, finalAllChars, finalParticipantIds);
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

    private void showManageDialog(List<String> currentIds, List<JSONObject> allChars, List<String> participantIds) {
        android.app.AlertDialog.Builder builder = new android.app.AlertDialog.Builder(getContext());
        builder.setTitle("Gestisci Chat di Gruppo");

        ScrollView scroll = new ScrollView(getContext());
        LinearLayout container = new LinearLayout(getContext());
        container.setOrientation(LinearLayout.VERTICAL);
        int pad = (int) (48 * getResources().getDisplayMetrics().density);
        container.setPadding(pad, 32, pad, 0);

        TextView charLabel = new TextView(getContext());
        charLabel.setText("Personaggi (" + currentIds.size() + "):");
        charLabel.setPadding(0, 0, 0, 8);
        charLabel.setTextColor(Color.parseColor("#E0E0E0"));
        container.addView(charLabel);

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
            String finalCharName = charName;
            charView.setOnClickListener(v -> removeCharacter(cid, finalCharName));
            container.addView(charView);
        }

        if (currentIds.size() < 8) {
            TextView addCharLabel = new TextView(getContext());
            addCharLabel.setText("\nAggiungi personaggio:");
            addCharLabel.setPadding(0, 16, 0, 8);
            addCharLabel.setTextColor(Color.parseColor("#E0E0E0"));
            container.addView(addCharLabel);

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
                    addView.setOnClickListener(v -> addCharacter(id, name));
                    container.addView(addView);
                }
            }
        }

        TextView partLabel = new TextView(getContext());
        partLabel.setText("\nUtenti (" + participantIds.size() + "):");
        partLabel.setPadding(0, 24, 0, 8);
        partLabel.setTextColor(Color.parseColor("#E0E0E0"));
        container.addView(partLabel);

        for (String pid : participantIds) {
            String displayName = userIdToName.get(pid);
            if (displayName == null) displayName = pid.length() > 8 ? pid.substring(0, 8) + "..." : pid;
            TextView partView = new TextView(getContext());
            partView.setText("✕ " + displayName);
            partView.setPadding(0, 8, 0, 8);
            partView.setTextColor(Color.parseColor("#FF8A80"));
            partView.setTextSize(14);
            partView.setOnClickListener(v -> removeParticipant(pid));
            container.addView(partView);
        }

        TextView addPartLabel = new TextView(getContext());
        addPartLabel.setText("\nInvita utente:");
        addPartLabel.setPadding(0, 16, 0, 8);
        addPartLabel.setTextColor(Color.parseColor("#E0E0E0"));
        container.addView(addPartLabel);

        EditText searchInput = new EditText(getContext());
        searchInput.setHint("Cerca username...");
        searchInput.setTextColor(Color.parseColor("#E0E0E0"));
        searchInput.setTextSize(14);
        container.addView(searchInput);

        LinearLayout searchResultsList = new LinearLayout(getContext());
        searchResultsList.setOrientation(LinearLayout.VERTICAL);
        container.addView(searchResultsList);

        searchInput.setOnEditorActionListener((v, actionId, event) -> {
            String query = searchInput.getText().toString().trim();
            if (!query.isEmpty()) {
                searchUsers(query, searchResultsList);
            }
            return true;
        });

        scroll.addView(container);
        builder.setView(scroll);
        builder.setNegativeButton("Chiudi", null);
        builder.show();
    }

    private void searchUsers(String query, LinearLayout resultsList) {
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
                        resultsList.removeAllViews();
                        if (results.isEmpty()) {
                            TextView noResult = new TextView(getContext());
                            noResult.setText("Nessun risultato");
                            noResult.setTextColor(Color.parseColor("#888888"));
                            resultsList.addView(noResult);
                            return;
                        }
                        for (JSONObject u : results) {
                            String uid = u.optString("id");
                            String username = u.optString("username", uid);
                            TextView userView = new TextView(getContext());
                            userView.setText("+ " + username);
                            userView.setPadding(0, 8, 0, 8);
                            userView.setTextColor(Color.parseColor("#4FC3F7"));
                            userView.setTextSize(14);
                            userView.setOnClickListener(v -> addParticipant(uid, username));
                            resultsList.addView(userView);
                        }
                    });
                }
            } catch (Exception e) {
                mainHandler.post(() -> {
                    resultsList.removeAllViews();
                    TextView errView = new TextView(getContext());
                    errView.setText("Errore ricerca");
                    errView.setTextColor(Color.parseColor("#FF8A80"));
                    resultsList.addView(errView);
                });
            }
        });
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

    private void addParticipant(String userId, String username) {
        loadingBar.setVisibility(View.VISIBLE);
        executor.execute(() -> {
            try {
                JSONObject body = new JSONObject();
                body.put("user_id", userId);
                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(
                    baseUrl + "/group-chats/" + chatId + "/participants",
                    "POST", body.toString(), 10000);
                mainHandler.post(() -> {
                    loadingBar.setVisibility(View.GONE);
                    if (resp.statusCode == 200 || resp.statusCode == 201) {
                        Toast.makeText(getContext(), "Invito inviato a " + username + "!", Toast.LENGTH_SHORT).show();
                        userIdToName.put(userId, username);
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

    private void removeParticipant(String userId) {
        new android.app.AlertDialog.Builder(getContext())
            .setTitle("Rimuovi " + userId + "?")
            .setMessage("Vuoi rimuovere questo utente dalla chat?")
            .setPositiveButton("Rimuovi", (d, w) -> {
                loadingBar.setVisibility(View.VISIBLE);
                executor.execute(() -> {
                    try {
                        AuthManager.HttpResponse resp = mAuth.requestWithRefresh(
                            baseUrl + "/group-chats/" + chatId + "/participants/" + userId,
                            "DELETE", null, 10000);
                        mainHandler.post(() -> {
                            loadingBar.setVisibility(View.GONE);
                            if (resp.statusCode == 200) {
                                Toast.makeText(getContext(), "Utente rimosso", Toast.LENGTH_SHORT).show();
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

    private void showContextMenu(View anchor, MessageItem item) {
        PopupMenu popup = new PopupMenu(anchor.getContext(), anchor);
        popup.getMenu().add(0, 1, 0, "Copia messaggio");
        popup.setOnMenuItemClickListener(menuItem -> {
            if (menuItem.getItemId() == 1) {
                ClipboardManager clipboard = (ClipboardManager) anchor.getContext().getSystemService(Context.CLIPBOARD_SERVICE);
                ClipData clip = ClipData.newPlainText("message", item.content);
                clipboard.setPrimaryClip(clip);
                Toast.makeText(anchor.getContext(), "Messaggio copiato", Toast.LENGTH_SHORT).show();
                return true;
            }
            return false;
        });
        popup.show();
    }

    private void copyChatToClipboard() {
        StringBuilder sb = new StringBuilder();
        String header = "Chat di gruppo: " + (chatName != null ? chatName : "");
        sb.append(header).append("\n").append("═══════════════════════════════").append("\n\n");

        for (MessageItem item : messages) {
            String text = item.content;
            if (text == null || text.isEmpty()) continue;
            sb.append(item.senderName).append(": ").append(text).append("\n\n");
        }

        if (getActivity() == null) return;
        ClipboardManager clipboard = (ClipboardManager)
                getActivity().getSystemService(Context.CLIPBOARD_SERVICE);
        ClipData clip = ClipData.newPlainText("chat", sb.toString().trim());
        clipboard.setPrimaryClip(clip);
        if (!isAdded()) return;
        Toast.makeText(getActivity(), "Conversazione copiata negli appunti", Toast.LENGTH_SHORT).show();
    }

    @Override
    public void onStart() {
        super.onStart();
        isCancelled = false;
        if (executor == null || executor.isShutdown()) {
            executor = Executors.newSingleThreadExecutor();
        }
    }

    @Override
    public void onStop() {
        super.onStop();
        isCancelled = true;
        if (executor != null && !executor.isShutdown()) {
            executor.shutdownNow();
            executor = null;
        }
        sending = false;
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

            tv.setOnLongClickListener(v -> {
                showContextMenu(v, item);
                return true;
            });
        }

        @Override
        public int getItemCount() { return messages.size(); }

        class VH extends RecyclerView.ViewHolder {
            VH(View itemView) { super(itemView); }
        }
    }
}
