package com.intelligame.chatai;

import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import java.util.List;

public class LogActivity extends AppCompatActivity {
    private TextView logTextView;
    private AppLogger appLogger;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        View contentView = getLayoutInflater().inflate(R.layout.activity_log, null);
        setContentView(contentView);

        appLogger = AppLogger.getInstance(this);
        logTextView = findViewById(R.id.logTextView);

        Button btnRefresh = findViewById(R.id.btnRefresh);
        Button btnSave = findViewById(R.id.btnSave);
        Button btnClear = findViewById(R.id.btnClear);
        Button btnCopy = findViewById(R.id.btnCopy);

        btnRefresh.setOnClickListener(v -> refreshLogs());
        btnSave.setOnClickListener(v -> saveLogs());
        btnClear.setOnClickListener(v -> clearLogs());
        btnCopy.setOnClickListener(v -> copyLogsToClipboard());

        refreshLogs();
    }

    private void refreshLogs() {
        List<String> logs = appLogger.getLogEntries();
        StringBuilder sb = new StringBuilder();

        sb.append("=== ChatAI App Runtime Logs ===\n");
        sb.append("Entries: ").append(logs.size()).append("\n\n");

        for (String log : logs) {
            sb.append(log).append("\n");
        }

        logTextView.setText(sb.toString());
    }

    private void saveLogs() {
        String result = appLogger.saveLogToDownloads();
        if (result.startsWith("Error")) {
            Toast.makeText(this, "Save failed: " + result, Toast.LENGTH_LONG).show();
        } else {
            Toast.makeText(this, "Log saved to Downloads", Toast.LENGTH_LONG).show();
        }
    }

    private void clearLogs() {
        appLogger.clearLogs();
        refreshLogs();
        Toast.makeText(this, "Logs cleared", Toast.LENGTH_SHORT).show();
    }

    private void copyLogsToClipboard() {
        CharSequence text = logTextView.getText();
        if (text == null || text.length() == 0) {
            Toast.makeText(this, "Nessun log da copiare", Toast.LENGTH_SHORT).show();
            return;
        }
        ClipboardManager clipboard = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
        if (clipboard == null) {
            Toast.makeText(this, "Clipboard non disponibile", Toast.LENGTH_SHORT).show();
            return;
        }
        clipboard.setPrimaryClip(ClipData.newPlainText("App Logs", text));
        Toast.makeText(this, "Log copiati negli appunti", Toast.LENGTH_SHORT).show();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        appLogger.shutdown();
    }
}
