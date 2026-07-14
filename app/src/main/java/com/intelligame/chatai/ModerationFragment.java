package com.intelligame.chatai;

import android.graphics.Color;
import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
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

public class ModerationFragment extends Fragment {

    private AuthManager mAuth;
    private RecyclerView flagsList;
    private ProgressBar loadingBar;
    private FlagAdapter adapter;

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater, @Nullable ViewGroup container, @Nullable Bundle savedInstanceState) {
        return inflater.inflate(R.layout.fragment_moderation, container, false);
    }

    @Override
    public void onViewCreated(@NonNull View view, @Nullable Bundle savedInstanceState) {
        super.onViewCreated(view, savedInstanceState);
        mAuth = ((ChatApplication) requireActivity().getApplication()).getAuthManager();

        flagsList = view.findViewById(R.id.flags_list);
        loadingBar = view.findViewById(R.id.loading_flags);
        view.findViewById(R.id.btn_refresh_flags).setOnClickListener(v -> loadFlags());

        flagsList.setLayoutManager(new LinearLayoutManager(getContext()));
        adapter = new FlagAdapter();
        flagsList.setAdapter(adapter);

        loadFlags();
    }

    private void loadFlags() {
        loadingBar.setVisibility(View.VISIBLE);
        new Thread(() -> {
            try {
                String url = ((ChatApplication) requireActivity().getApplication()).getCurrentUrl()
                        + "/admin/flags?resolved=false";
                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(url, "GET", null, 10000);
                if (resp.statusCode == 200) {
                    JSONArray arr = new JSONArray(resp.body);
                    List<FlagItem> flags = new ArrayList<>();
                    for (int i = 0; i < arr.length(); i++) {
                        JSONObject obj = arr.getJSONObject(i);
                        FlagItem item = new FlagItem();
                        item.id = obj.optInt("id", 0);
                        item.reason = obj.optString("reason", "");
                        item.contentSnippet = obj.optString("content_snippet", "");
                        item.severity = obj.optString("severity", "");
                        item.createdAt = obj.optString("created_at", "");
                        flags.add(item);
                    }
                    if (getActivity() != null) {
                        getActivity().runOnUiThread(() -> {
                            adapter.setFlags(flags);
                            loadingBar.setVisibility(View.GONE);
                        });
                    }
                }
            } catch (Exception e) {
                if (getActivity() != null) {
                    getActivity().runOnUiThread(() -> {
                        loadingBar.setVisibility(View.GONE);
                        Toast.makeText(getContext(), "Errore caricamento flag", Toast.LENGTH_SHORT).show();
                    });
                }
            }
        }).start();
    }

    static class FlagItem {
        int id;
        String reason, contentSnippet, severity, createdAt;
    }

    class FlagAdapter extends RecyclerView.Adapter<FlagAdapter.VH> {
        private List<FlagItem> flags = new ArrayList<>();

        void setFlags(List<FlagItem> list) {
            this.flags = list;
            notifyDataSetChanged();
        }

        @NonNull
        @Override
        public VH onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
            View v = LayoutInflater.from(parent.getContext()).inflate(R.layout.item_flag, parent, false);
            return new VH(v);
        }

        @Override
        public void onBindViewHolder(@NonNull VH holder, int position) {
            FlagItem item = flags.get(position);
            holder.reason.setText(item.reason);
            holder.content.setText(item.contentSnippet);
            String ts = item.createdAt;
            holder.date.setText(ts.length() > 19 ? ts.substring(0, 19) : ts);

            holder.severity.setText(item.severity);
            int sevColor;
            switch (item.severity.toLowerCase()) {
                case "high": case "critical": sevColor = Color.parseColor("#FF5252"); break;
                case "medium": sevColor = Color.parseColor("#FFC107"); break;
                default: sevColor = Color.parseColor("#4CAF50"); break;
            }
            holder.severity.setBackgroundColor(sevColor);
            holder.severity.setTextColor(Color.WHITE);

            holder.resolve.setOnClickListener(v -> resolveFlag(item.id, holder));
        }

        @Override
        public int getItemCount() { return flags.size(); }

        class VH extends RecyclerView.ViewHolder {
            TextView reason, content, severity, date;
            Button resolve;
            VH(View v) {
                super(v);
                reason = v.findViewById(R.id.flag_reason);
                content = v.findViewById(R.id.flag_content);
                severity = v.findViewById(R.id.flag_severity);
                date = v.findViewById(R.id.flag_date);
                resolve = v.findViewById(R.id.btn_resolve);
            }
        }
    }

    private void resolveFlag(int flagId, FlagAdapter.VH holder) {
        holder.resolve.setEnabled(false);
        new Thread(() -> {
            try {
                String url = ((ChatApplication) requireActivity().getApplication()).getCurrentUrl()
                        + "/admin/flags/" + flagId + "/resolve";
                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(url, "POST", null, 10000);
                if (resp.statusCode == 200) {
                    if (getActivity() != null) {
                        getActivity().runOnUiThread(() -> {
                            Toast.makeText(getContext(), "Flag risolto", Toast.LENGTH_SHORT).show();
                            loadFlags();
                        });
                    }
                }
            } catch (Exception e) {
                if (getActivity() != null) {
                    getActivity().runOnUiThread(() -> {
                        holder.resolve.setEnabled(true);
                        Toast.makeText(getContext(), "Errore risoluzione flag", Toast.LENGTH_SHORT).show();
                    });
                }
            }
        }).start();
    }
}
