package com.intelligame.chatai;

import android.app.AlertDialog;
import android.app.Dialog;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.DialogFragment;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class DailyBonusDialog extends DialogFragment {

    private static final String TAG = "DailyBonusDialog";
    private ExecutorService executor = Executors.newSingleThreadExecutor();
    private Handler mainHandler = new Handler(Looper.getMainLooper());

    @NonNull
    @Override
    public Dialog onCreateDialog(@Nullable Bundle savedInstanceState) {
        View view = requireActivity().getLayoutInflater().inflate(R.layout.dialog_daily_bonus, null);
        
        TextView titleText = view.findViewById(R.id.bonus_title);
        TextView rewardText = view.findViewById(R.id.bonus_reward_text);
        TextView streakText = view.findViewById(R.id.bonus_streak_text);
        
        titleText.setText("Bonus Giornaliero!");
        rewardText.setText("Caricamento...");
        streakText.setText("");

        checkAndShowBonus(view);

        AlertDialog.Builder builder = new AlertDialog.Builder(requireActivity());
        builder.setView(view)
               .setPositiveButton("Riscuoti", (dialog, which) -> claimDailyBonus())
               .setNegativeButton("Più tardi", (dialog, which) -> dialog.dismiss());
        
        AlertDialog dialog = builder.create();
        dialog.setCancelable(false);
        return dialog;
    }

    private void checkAndShowBonus(View view) {
        TextView rewardText = view.findViewById(R.id.bonus_reward_text);
        TextView streakText = view.findViewById(R.id.bonus_streak_text);

        executor.execute(() -> {
            try {
                ChatApplication app = (ChatApplication) requireActivity().getApplication();
                AuthManager auth = app.getAuthManager();
                String baseUrl = app.getPrefs().getServerUrl().replace("/chat", "");
                String token = auth.getAccessToken();

                URL url = new URL(baseUrl + "/user/mevacoins/streak");
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestProperty("Authorization", "Bearer " + token);
                conn.setConnectTimeout(5000);
                
                if (conn.getResponseCode() == 200) {
                    BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                    StringBuilder resp = new StringBuilder();
                    String line;
                    while ((line = reader.readLine()) != null) resp.append(line);
                    reader.close();
                    
                    JSONObject result = new JSONObject(resp.toString());
                    int currentDay = result.optInt("current_day", 1);
                    boolean alreadyClaimed = result.optBoolean("already_claimed_today", false);
                    int reward = calculateReward(currentDay);
                    
                    mainHandler.post(() -> {
                        if (isAdded()) {
                            if (alreadyClaimed) {
                                rewardText.setText("✓ Già riscosso oggi!");
                                streakText.setText("Torna domani per il giorno " + (currentDay + 1));
                                if (getDialog() != null) {
                                    ((AlertDialog) getDialog()).getButton(AlertDialog.BUTTON_POSITIVE).setEnabled(false);
                                }
                            } else {
                                rewardText.setText("+" + reward + " MVC");
                                streakText.setText("Giorno " + currentDay + " di 30" + 
                                    (currentDay == 30 ? "\n🎉 SUPER BONUS!" : ""));
                            }
                        }
                    });
                }
                conn.disconnect();
            } catch (Exception e) {
                mainHandler.post(() -> {
                    if (isAdded()) {
                        rewardText.setText("+10 MVC");
                        streakText.setText("Giorno 1 di 30");
                    }
                });
            }
        });
    }

    private void claimDailyBonus() {
        executor.execute(() -> {
            try {
                ChatApplication app = (ChatApplication) requireActivity().getApplication();
                AuthManager auth = app.getAuthManager();
                String baseUrl = app.getPrefs().getServerUrl().replace("/chat", "");
                String token = auth.getAccessToken();

                URL url = new URL(baseUrl + "/user/mevacoins/streak/claim");
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("POST");
                conn.setDoOutput(true);
                conn.setRequestProperty("Authorization", "Bearer " + token);
                conn.setRequestProperty("Content-Type", "application/json");
                conn.setConnectTimeout(5000);

                JSONObject body = new JSONObject();
                body.put("day", 0);
                OutputStream os = conn.getOutputStream();
                os.write(body.toString().getBytes());
                os.close();

                BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                StringBuilder resp = new StringBuilder();
                String line;
                while ((line = reader.readLine()) != null) resp.append(line);
                reader.close();
                conn.disconnect();

                JSONObject result = new JSONObject(resp.toString());
                int earned = result.optInt("earned", 10);

                mainHandler.post(() -> {
                    if (isAdded()) {
                        if (getDialog() != null) getDialog().dismiss();
                        if (getActivity() != null) {
                            com.google.android.material.snackbar.Snackbar.make(
                                getActivity().findViewById(android.R.id.content),
                                "+" + earned + " MVC riscossi!",
                                com.google.android.material.snackbar.Snackbar.LENGTH_LONG).show();
                        }
                    }
                });
            } catch (Exception e) {
                mainHandler.post(() -> {
                    if (isAdded() && getDialog() != null) getDialog().dismiss();
                });
            }
        });
    }

    private int calculateReward(int day) {
        if (day >= 30) return 100;
        return 10 + (day - 1) * 2;
    }

    @Override
    public void onDestroyView() {
        super.onDestroyView();
        if (executor != null) executor.shutdownNow();
    }
}
