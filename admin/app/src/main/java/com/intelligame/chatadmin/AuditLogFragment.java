package com.intelligame.chatadmin;

import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
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

public class AuditLogFragment extends Fragment {

    private AuthManager mAuth;
    private RecyclerView logsList;
    private ProgressBar loadingBar;
    private LogAdapter adapter;

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater, @Nullable ViewGroup container, @Nullable Bundle savedInstanceState) {
        return inflater.inflate(R.layout.fragment_audit_log, container, false);
    }

    @Override
    public void onViewCreated(@NonNull View view, @Nullable Bundle savedInstanceState) {
        super.onViewCreated(view, savedInstanceState);
        mAuth = ((ChatApplication) requireActivity().getApplication()).getAuthManager();

        logsList = view.findViewById(R.id.logs_list);
        loadingBar = view.findViewById(R.id.loading_logs);
        view.findViewById(R.id.btn_refresh_logs).setOnClickListener(v -> loadLogs());

        logsList.setLayoutManager(new LinearLayoutManager(getContext()));
        adapter = new LogAdapter();
        logsList.setAdapter(adapter);

        loadLogs();
    }

    private void loadLogs() {
        loadingBar.setVisibility(View.VISIBLE);
        new Thread(() -> {
            try {
                String url = ((ChatApplication) requireActivity().getApplication()).getCurrentUrl()
                        + "/admin/logs?limit=200";
                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(url, "GET", null, 10000);
                if (resp.statusCode == 200) {
                    JSONArray arr = new JSONArray(resp.body);
                    List<LogItem> logs = new ArrayList<>();
                    for (int i = 0; i < arr.length(); i++) {
                        JSONObject obj = arr.getJSONObject(i);
                        LogItem item = new LogItem();
                        item.action = obj.optString("action", "");
                        item.detail = obj.optString("detail", "");
                        item.ip = obj.optString("ip", "");
                        item.timestamp = obj.optString("timestamp", "");
                        logs.add(item);
                    }
                    if (getActivity() != null) {
                        getActivity().runOnUiThread(() -> {
                            adapter.setLogs(logs);
                            loadingBar.setVisibility(View.GONE);
                        });
                    }
                }
            } catch (Exception e) {
                if (getActivity() != null) {
                    getActivity().runOnUiThread(() -> {
                        loadingBar.setVisibility(View.GONE);
                        Toast.makeText(getContext(), "Errore caricamento log", Toast.LENGTH_SHORT).show();
                    });
                }
            }
        }).start();
    }

    static class LogItem {
        String action, detail, ip, timestamp;
    }

    class LogAdapter extends RecyclerView.Adapter<LogAdapter.VH> {
        private List<LogItem> logs = new ArrayList<>();

        void setLogs(List<LogItem> list) {
            this.logs = list;
            notifyDataSetChanged();
        }

        @NonNull
        @Override
        public VH onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
            View v = LayoutInflater.from(parent.getContext()).inflate(R.layout.item_log_entry, parent, false);
            return new VH(v);
        }

        @Override
        public void onBindViewHolder(@NonNull VH holder, int position) {
            LogItem item = logs.get(position);
            holder.action.setText(item.action);
            holder.detail.setText(item.detail);
            String ts = item.timestamp;
            holder.timestamp.setText(ts.length() > 19 ? ts.substring(0, 19) : ts);
            holder.userIp.setText("IP: " + item.ip);
        }

        @Override
        public int getItemCount() { return logs.size(); }

        class VH extends RecyclerView.ViewHolder {
            TextView action, detail, timestamp, userIp;
            VH(View v) {
                super(v);
                action = v.findViewById(R.id.log_action);
                detail = v.findViewById(R.id.log_detail);
                timestamp = v.findViewById(R.id.log_timestamp);
                userIp = v.findViewById(R.id.log_user_ip);
            }
        }
    }
}
