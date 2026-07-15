package com.intelligame.chatadmin;

import android.app.AlertDialog;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.EditText;
import android.widget.LinearLayout;
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

public class ChatViewerFragment extends Fragment {

    private static final String ARG_USER_ID = "user_id";
    private AuthManager mAuth;
    private String userId;
    private RecyclerView listConversations;
    private RecyclerView listMessages;
    private LinearLayout emptyView;
    private TextView titleView;
    private LinearLayout msgInputArea;

    public static ChatViewerFragment newInstance(String userId) {
        ChatViewerFragment f = new ChatViewerFragment();
        Bundle args = new Bundle();
        args.putString(ARG_USER_ID, userId);
        f.setArguments(args);
        return f;
    }

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater, @Nullable ViewGroup container, @Nullable Bundle savedInstanceState) {
        return inflater.inflate(R.layout.fragment_chat_viewer, container, false);
    }

    @Override
    public void onViewCreated(@NonNull View view, @Nullable Bundle savedInstanceState) {
        super.onViewCreated(view, savedInstanceState);
        mAuth = ((ChatApplication) requireActivity().getApplication()).getAuthManager();
        userId = getArguments() != null ? getArguments().getString(ARG_USER_ID) : "";

        listConversations = view.findViewById(R.id.bcv_list);
        listConversations.setLayoutManager(new LinearLayoutManager(getContext()));

        listMessages = view.findViewById(R.id.bcv_messages);
        listMessages.setLayoutManager(new LinearLayoutManager(getContext()));

        emptyView = view.findViewById(R.id.bcv_empty);
        titleView = view.findViewById(R.id.bcv_title);
        msgInputArea = view.findViewById(R.id.bcv_msg_input_area);

        view.findViewById(R.id.bcv_back).setOnClickListener(v -> {
            if (listMessages.getVisibility() == View.VISIBLE) {
                showConversationsList();
            } else {
                ((MainActivity) requireActivity()).onBackPressed();
            }
        });

        view.findViewById(R.id.bcv_dm).setOnClickListener(v -> showSendDmDialog());

        loadConversations();
    }

    private void loadConversations() {
        showLoading(true);
        new Thread(() -> {
            try {
                String url = ((ChatApplication) requireActivity().getApplication()).getCurrentUrl()
                        + "/admin/users/" + userId + "/conversations";
                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(url, "GET", null, 10000);
                if (resp.statusCode == 200) {
                    JSONArray arr = new JSONArray(resp.body);
                    if (getActivity() != null) {
                        getActivity().runOnUiThread(() -> {
                            showLoading(false);
                            if (arr.length() == 0) {
                                listConversations.setVisibility(View.GONE);
                                emptyView.setVisibility(View.VISIBLE);
                            } else {
                                emptyView.setVisibility(View.GONE);
                                listConversations.setVisibility(View.VISIBLE);
                                listConversations.setAdapter(new ConversationAdapter(arr));
                            }
                        });
                    }
                }
            } catch (Exception e) {
                if (getActivity() != null) {
                    getActivity().runOnUiThread(() -> {
                        showLoading(false);
                        Toast.makeText(getContext(), "Errore caricamento conversazioni", Toast.LENGTH_SHORT).show();
                    });
                }
            }
        }).start();
    }

    private void loadMessages(String characterId, String characterName) {
        titleView.setText(characterName);
        showLoading(true);
        listConversations.setVisibility(View.GONE);
        emptyView.setVisibility(View.GONE);

        new Thread(() -> {
            try {
                String url = ((ChatApplication) requireActivity().getApplication()).getCurrentUrl()
                        + "/admin/users/" + userId + "/conversations/" + characterId;
                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(url, "GET", null, 10000);
                if (resp.statusCode == 200) {
                    JSONObject wrapper = new JSONObject(resp.body);
                    JSONArray rawArr = wrapper.optJSONArray("messages");
                    final JSONArray arr = (rawArr != null) ? rawArr : new JSONArray();
                    if (getActivity() != null) {
                        getActivity().runOnUiThread(() -> {
                            showLoading(false);
                            listMessages.setVisibility(View.VISIBLE);
                            msgInputArea.setVisibility(View.VISIBLE);
                            if (arr.length() == 0) {
                                emptyView.setVisibility(View.VISIBLE);
                            } else {
                                emptyView.setVisibility(View.GONE);
                            }
                            listMessages.setAdapter(new MessageAdapter(arr));
                            if (arr.length() > 0) {
                                listMessages.scrollToPosition(arr.length() - 1);
                            }
                        });
                    }
                }
            } catch (Exception e) {
                if (getActivity() != null) {
                    getActivity().runOnUiThread(() -> {
                        showLoading(false);
                        Toast.makeText(getContext(), "Errore caricamento messaggi", Toast.LENGTH_SHORT).show();
                    });
                }
            }
        }).start();
    }

    private void showConversationsList() {
        listMessages.setVisibility(View.GONE);
        msgInputArea.setVisibility(View.GONE);
        titleView.setText("Conversazioni");
        emptyView.setVisibility(View.GONE);
        listConversations.setVisibility(View.VISIBLE);
    }

    private void showSendDmDialog() {
        EditText input = new EditText(getContext());
        input.setHint("Scrivi messaggio privato...");
        input.setMinLines(3);
        input.setMaxLines(6);
        input.setPadding(48, 32, 48, 16);

        new AlertDialog.Builder(getContext())
            .setTitle("Messaggio Privato a " + userId.substring(0, Math.min(8, userId.length())) + "...")
            .setView(input)
            .setPositiveButton("Invia", (dialog, which) -> {
                String text = input.getText().toString().trim();
                if (!text.isEmpty()) sendDm(text);
            })
            .setNegativeButton("Annulla", null)
            .show();
    }

    private void sendDm(String content) {
        new Thread(() -> {
            try {
                String url = ((ChatApplication) requireActivity().getApplication()).getCurrentUrl()
                        + "/admin/users/" + userId + "/dm";
                JSONObject body = new JSONObject();
                body.put("content", content);
                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(url, "POST", body.toString(), 10000);
                if (resp.statusCode == 200) {
                    if (getActivity() != null) {
                        getActivity().runOnUiThread(() ->
                            Toast.makeText(getContext(), "Messaggio inviato", Toast.LENGTH_SHORT).show());
                    }
                } else {
                    if (getActivity() != null) {
                        getActivity().runOnUiThread(() ->
                            Toast.makeText(getContext(), "Errore invio: " + resp.statusCode, Toast.LENGTH_SHORT).show());
                    }
                }
            } catch (Exception e) {
                if (getActivity() != null) {
                    getActivity().runOnUiThread(() ->
                        Toast.makeText(getContext(), "Errore connessione", Toast.LENGTH_SHORT).show());
                }
            }
        }).start();
    }

    private void showLoading(boolean show) {
        if (getView() != null) {
            getView().findViewById(R.id.bcv_progress).setVisibility(show ? View.VISIBLE : View.GONE);
        }
    }

    // ─── Conversation Adapter ─────────────────────────────────────
    private class ConversationAdapter extends RecyclerView.Adapter<ConversationAdapter.VH> {
        private final JSONArray items;
        ConversationAdapter(JSONArray arr) { items = arr; }

        @NonNull
        @Override
        public VH onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
            TextView tv = new TextView(parent.getContext());
            tv.setLayoutParams(new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
            int pad = (int)(parent.getContext().getResources().getDisplayMetrics().density * 14);
            tv.setPadding(pad, pad, pad, pad);
            tv.setTextSize(15);
            tv.setTextColor(Color.parseColor("#E0E0E0"));
            tv.setBackgroundColor(Color.parseColor("#1E1E2E"));
            android.view.ViewGroup.MarginLayoutParams mp = (android.view.ViewGroup.MarginLayoutParams) tv.getLayoutParams();
            mp.bottomMargin = (int)(parent.getContext().getResources().getDisplayMetrics().density * 6);
            tv.setLayoutParams(mp);
            return new VH(tv);
        }

        @Override
        public void onBindViewHolder(@NonNull VH holder, int position) {
            try {
                JSONObject item = items.getJSONObject(position);
                String charId = item.optString("character_id", "");
                String charName = item.optString("character_name", charId);
                int msgCount = item.optInt("msg_count", 0);
                String lastMsg = item.optString("last_msg", "");
                if (lastMsg.length() > 16) lastMsg = lastMsg.substring(0, 16);

                String display = "\ud83d\udcac " + charName + "  (" + msgCount + " msg)\n"
                    + "Ultimo: " + lastMsg;

                ((TextView) holder.itemView).setText(display);
                ((TextView) holder.itemView).setOnClickListener(v ->
                    loadMessages(charId, charName));
            } catch (Exception ignored) {}
        }

        @Override
        public int getItemCount() { return items.length(); }

        class VH extends RecyclerView.ViewHolder {
            VH(View v) { super(v); }
        }
    }

    // ─── Message Adapter ──────────────────────────────────────────
    private class MessageAdapter extends RecyclerView.Adapter<MessageAdapter.VH> {
        private final JSONArray items;
        MessageAdapter(JSONArray arr) { items = arr; }

        @NonNull
        @Override
        public VH onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
            LinearLayout layout = new LinearLayout(parent.getContext());
            layout.setLayoutParams(new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
            layout.setOrientation(LinearLayout.VERTICAL);
            int pad = (int)(parent.getContext().getResources().getDisplayMetrics().density * 12);
            layout.setPadding(pad, pad/2, pad, pad/2);

            TextView roleText = new TextView(parent.getContext());
            roleText.setTextSize(11);
            roleText.setTypeface(null, Typeface.BOLD);

            TextView contentText = new TextView(parent.getContext());
            contentText.setTextSize(14);

            TextView timeText = new TextView(parent.getContext());
            timeText.setTextSize(10);
            timeText.setTextColor(Color.parseColor("#9E9E9E"));

            layout.addView(roleText);
            layout.addView(contentText);
            layout.addView(timeText);
            return new VH(layout, roleText, contentText, timeText);
        }

        @Override
        public void onBindViewHolder(@NonNull VH holder, int position) {
            try {
                JSONObject msg = items.getJSONObject(position);
                String role = msg.optString("role", "");
                String content = msg.optString("content", "");
                String timestamp = msg.optString("timestamp", "");
                if (timestamp.length() > 19) timestamp = timestamp.substring(0, 19);

                String roleDisplay;
                int roleColor;
                if ("user".equals(role)) {
                    roleDisplay = "\ud83d\udc64 Utente";
                    roleColor = Color.parseColor("#4FC3F7");
                } else if ("assistant".equals(role)) {
                    roleDisplay = "\ud83e\udd16 AI";
                    roleColor = Color.parseColor("#CE93D8");
                } else if ("system".equals(role)) {
                    roleDisplay = "\ud83d\udce2 Sistema";
                    roleColor = Color.parseColor("#FFB74D");
                } else {
                    roleDisplay = role;
                    roleColor = Color.parseColor("#9E9E9E");
                }

                holder.roleView.setText(roleDisplay);
                holder.roleView.setTextColor(roleColor);
                holder.contentView.setText(content);
                holder.contentView.setTextColor(Color.parseColor("#E0E0E0"));
                holder.timeView.setText(timestamp);

                int density = (int)(holder.itemView.getContext().getResources().getDisplayMetrics().density * 4);
                android.view.ViewGroup.LayoutParams lp = holder.itemView.getLayoutParams();
                if (lp instanceof android.view.ViewGroup.MarginLayoutParams) {
                    ((android.view.ViewGroup.MarginLayoutParams) lp).bottomMargin = density;
                }
            } catch (Exception ignored) {}
        }

        @Override
        public int getItemCount() { return items.length(); }

        class VH extends RecyclerView.ViewHolder {
            TextView roleView, contentView, timeView;
            VH(View itemView, TextView r, TextView c, TextView t) {
                super(itemView);
                this.roleView = r;
                this.contentView = c;
                this.timeView = t;
            }
        }
    }
}
