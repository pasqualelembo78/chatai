package com.intelligame.chatai;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.Environment;
import android.util.Log;

import java.io.BufferedWriter;
import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class AppLogger {
    private static AppLogger instance;
    private final List<String> logBuffer;
    private final ExecutorService executor;
    private final File logFile;
    private final Context context;
    private final int maxEntries = 500;

    private AppLogger(Context context) {
        this.context = context.getApplicationContext();
        logBuffer = new ArrayList<>();
        executor = Executors.newSingleThreadExecutor();
        
        File logsDir = new File(context.getExternalFilesDir(null), "logs");
        if (!logsDir.exists()) {
            logsDir.mkdirs();
        }
        
        String timestamp = new SimpleDateFormat("yyyyMMdd_HHmmss", Locale.getDefault()).format(new Date());
        logFile = new File(logsDir, "app_log_" + timestamp + ".txt");
    }

    public static synchronized AppLogger getInstance(Context context) {
        if (instance == null) {
            instance = new AppLogger(context.getApplicationContext());
        }
        return instance;
    }

    private String getTimestamp() {
        return new SimpleDateFormat("HH:mm:ss.SSS", Locale.getDefault()).format(new Date());
    }

    public void log(String tag, String message) {
        String entry = "[" + getTimestamp() + "] [" + tag + "] " + message;
        
        logBuffer.add(entry);
        if (logBuffer.size() > maxEntries) {
            logBuffer.remove(0);
        }
        
        executor.execute(() -> writeToFile(entry));
        Log.d("ChatAI_" + tag, message);
    }

    public void info(String tag, String message) {
        log(tag, "ℹ️ " + message);
    }

    public void error(String tag, String message) {
        log(tag, "❌ " + message);
    }

    public void success(String tag, String message) {
        log(tag, "✅ " + message);
    }

    public void debug(String tag, String message) {
        log(tag, "🔍 " + message);
    }

    public void warn(String tag, String message) {
        log(tag, "⚠️ " + message);
    }

    private void writeToFile(String entry) {
        try (BufferedWriter writer = new BufferedWriter(new FileWriter(logFile, true))) {
            writer.write(entry);
            writer.newLine();
        } catch (IOException e) {
            Log.e("AppLogger", "Error writing to log file", e);
        }
    }

    public List<String> getLogEntries() {
        return new ArrayList<>(logBuffer);
    }

    public String getLogText() {
        StringBuilder sb = new StringBuilder();
        for (String entry : logBuffer) {
            sb.append(entry).append("\n");
        }
        return sb.toString();
    }

    public File getLogFile() {
        return logFile;
    }

    public void clearLogs() {
        logBuffer.clear();
        if (logFile.exists()) {
            logFile.delete();
        }
    }

    public String saveLogToDownloads() {
        try {
            String timestamp = new SimpleDateFormat("yyyyMMdd_HHmmss", Locale.getDefault()).format(new Date());
            File downloadsDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS);
            File savedFile = new File(downloadsDir, "chatai_log_" + timestamp + ".txt");
            
            try (BufferedWriter writer = new BufferedWriter(new FileWriter(savedFile))) {
                writer.write("=== ChatAI App Log ===\n");
                writer.write("Date: " + new SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault()).format(new Date()) + "\n");
                writer.write("Device: " + android.os.Build.MODEL + "\n");
                writer.write("Android Version: " + android.os.Build.VERSION.RELEASE + "\n");
                writer.write("App Version: " + ChatApplication.getAppVersion(context) + "\n");
                writer.write("========================================\n\n");
                
                for (String entry : logBuffer) {
                    writer.write(entry);
                    writer.newLine();
                }
            }
            
            return savedFile.getAbsolutePath();
        } catch (IOException e) {
            return "Error: " + e.getMessage();
        }
    }

    public void shutdown() {
        executor.shutdown();
    }
}
