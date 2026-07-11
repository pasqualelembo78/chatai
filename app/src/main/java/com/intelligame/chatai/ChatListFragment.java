package com.intelligame.chatai;

import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.Fragment;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class ChatListFragment extends Fragment {

    private RecyclerView chatList;
    private TextView emptyText;
    private ExecutorService executor = Executors.newSingleThreadExecutor();
    private Handler mainHandler = new Handler(Looper.getMainLooper());
    private String baseUrl;
    private String userId;
    private ChatConversationAdapter adapter;

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater, @Nullable ViewGroup container, @Nullable Bundle savedInstanceState) {
        View view = inflater.inflate(R.layout.fragment_chat_list, container, false);

        ChatApplication app = (ChatApplication) requireActivity().getApplication();
        PrefsManager prefs = app.getPrefs();
        baseUrl = prefs.getServerUrl().replace("/chat", "");
        userId = prefs.getUsername();

        chatList = view.findViewById(R.id.chat_list);
        emptyText = view.findViewById(R.id.empty_text);

        chatList.setLayoutManager(new LinearLayoutManager(requireContext()));
        adapter = new ChatConversationAdapter();
        chatList.setAdapter(adapter);

        loadConversations();

        return view;
    }

    private void loadConversations() {
        executor.execute(() -> {
            try {
                ChatApplication app = (ChatApplication) requireActivity().getApplication();
                List<JSONObject> localConvs = app.getLocalDb().getAllConversations();
                List<ConversationItem> items = new ArrayList<>();
                for (JSONObject obj : localConvs) {
                    String cid = obj.optString("character_id", "");
                    int count = obj.optInt("msg_count", 0);
                    String lastActive = obj.optString("last_active", "");
                    String cname = cid;
                    String cavatar = "💬";
                    try {
                        String json = httpGet(baseUrl + "/characters/" + cid);
                        if (json != null) {
                            JSONObject charObj = new JSONObject(json);
                            cname = charObj.optString("name", cid);
                            cavatar = charObj.optString("avatar", "💬");
                        }
                    } catch (Exception ignored) {}
                    items.add(new ConversationItem(cid, cname, cavatar, count, lastActive));
                }
                mainHandler.post(() -> {
                    if (items.isEmpty()) {
                        chatList.setVisibility(View.GONE);
                        emptyText.setVisibility(View.VISIBLE);
                    } else {
                        chatList.setVisibility(View.VISIBLE);
                        emptyText.setVisibility(View.GONE);
                        adapter.setData(items);
                    }
                });
            } catch (Exception ignored) {}
        });
    }

    private String httpGet(String urlStr) {
        try {
            URL url = new URL(urlStr);
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setConnectTimeout(5000);
            conn.setReadTimeout(5000);
            BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()));
            StringBuilder sb = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) sb.append(line);
            reader.close();
            return sb.toString();
        } catch (Exception e) {
            return null;
        }
    }

    static class ConversationItem {
        String characterId;
        String characterName;
        String characterAvatar;
        int messageCount;
        String lastActive;

        ConversationItem(String id, String name, String avatar, int count, String last) {
            this.characterId = id;
            this.characterName = name;
            this.characterAvatar = avatar;
            this.messageCount = count;
            this.lastActive = last;
        }
    }

    private class ChatConversationAdapter extends RecyclerView.Adapter<ChatConversationAdapter.ViewHolder> {
        private List<ConversationItem> data = new ArrayList<>();

        void setData(List<ConversationItem> items) {
            data = items;
            notifyDataSetChanged();
        }

        @NonNull
        @Override
        public ViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
            View v = LayoutInflater.from(parent.getContext())
                .inflate(android.R.layout.simple_list_item_2, parent, false);
            return new ViewHolder(v);
        }

        @Override
        public void onBindViewHolder(@NonNull ViewHolder holder, int position) {
            ConversationItem item = data.get(position);
            holder.text1.setText(item.characterAvatar + " " + item.characterName);
            holder.text2.setText(item.messageCount + " messaggi");
            holder.itemView.setOnClickListener(v -> {
                if (getActivity() instanceof MainActivity) {
                    ((MainActivity) getActivity()).openChat(item.characterId, item.characterName);
                }
            });
        }

        @Override
        public int getItemCount() { return data.size(); }

        class ViewHolder extends RecyclerView.ViewHolder {
            TextView text1, text2;
            ViewHolder(View v) {
                super(v);
                text1 = v.findViewById(android.R.id.text1);
                text2 = v.findViewById(android.R.id.text2);
                text1.setTextColor(getResources().getColor(R.color.on_surface));
                text2.setTextColor(getResources().getColor(R.color.on_surface_variant));
            }
        }
    }
}
