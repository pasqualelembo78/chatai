package com.intelligame.chatai;

import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;

import com.google.android.material.button.MaterialButton;
import com.google.android.material.snackbar.Snackbar;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MvcEarnActivity extends AppCompatActivity {

    private static final int[] BONUS_DAYS = {1, 2, 3, 4};

    private TextView balanceText;
    private TextView checkinStatusText;
    private MaterialButton btnCheckin;
    private MaterialButton btnWatchAd;
    private LinearLayout transactionsContainer;
    private TextView transactionsEmpty;

    private String baseUrl;
    private AuthManager mAuth;
    private ExecutorService executor = Executors.newSingleThreadExecutor();
    private Handler mainHandler = new Handler(Looper.getMainLooper());

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_mvc_earn);

        ChatApplication app = (ChatApplication) getApplication();
        mAuth = app.getAuthManager();
        baseUrl = app.getPrefs().getServerUrl().replace("/chat", "");

        balanceText = findViewById(R.id.earn_balance_text);
        checkinStatusText = findViewById(R.id.checkin_status_text);
        btnCheckin = findViewById(R.id.btn_do_checkin);
        btnWatchAd = findViewById(R.id.btn_watch_ad);
        transactionsContainer = findViewById(R.id.transactions_container);
        transactionsEmpty = findViewById(R.id.transactions_empty);

        btnCheckin.setOnClickListener(v -> doCheckin());

        // Rewarded video button
        btnWatchAd.setOnClickListener(v -> showRewardedAd());
        updateRewardedButton();

        for (int day : BONUS_DAYS) {
            int resId = getResources().getIdentifier("btn_claim_bonus_" + day, "id", getPackageName());
            MaterialButton btn = findViewById(resId);
            btn.setOnClickListener(v -> claimBonus(day));
        }

        loadAllData();
    }

    private void loadAllData() {
        loadBalance();
        loadBonusStatus();
        loadTransactions();
    }

    private void loadBalance() {
        executor.execute(() -> {
            try {
                String token = mAuth.getAccessToken();
                URL url = new URL(baseUrl + "/user/mevacoins");
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestProperty("Authorization", "Bearer " + token);
                conn.setConnectTimeout(5000);
                BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                StringBuilder resp = new StringBuilder();
                String line;
                while ((line = reader.readLine()) != null) resp.append(line);
                reader.close();
                conn.disconnect();
                JSONObject obj = new JSONObject(resp.toString());
                int balance = obj.optInt("balance", 0);
                mainHandler.post(() -> balanceText.setText(String.valueOf(balance)));
            } catch (Exception ignored) {}
        });
    }

    private void loadBonusStatus() {
        executor.execute(() -> {
            try {
                String token = mAuth.getAccessToken();
                URL url = new URL(baseUrl + "/user/mevacoins/new-user-bonus");
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestProperty("Authorization", "Bearer " + token);
                conn.setConnectTimeout(5000);
                BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                StringBuilder resp = new StringBuilder();
                String line;
                while ((line = reader.readLine()) != null) resp.append(line);
                reader.close();
                conn.disconnect();

                JSONArray arr = new JSONArray(resp.toString());
                // Determine which days are claimable: first unclaimed day is available,
                // subsequent days require previous to be claimed first
                boolean previousClaimed = true;
                for (int i = 0; i < arr.length(); i++) {
                    JSONObject day = arr.getJSONObject(i);
                    int dayNumber = day.optInt("day_number", i + 1);
                    boolean claimed = day.optInt("claimed", 0) == 1;

                    updateBonusDayUI(dayNumber, claimed, previousClaimed);
                    if (!claimed) previousClaimed = false;
                }
            } catch (Exception ignored) {}
        });
    }

    private void updateBonusDayUI(int dayNumber, boolean claimed, boolean available) {
        mainHandler.post(() -> {
            int statusResId = getResources().getIdentifier("bonus_status_" + dayNumber, "id", getPackageName());
            int btnResId = getResources().getIdentifier("btn_claim_bonus_" + dayNumber, "id", getPackageName());
            int cardResId = getResources().getIdentifier("bonus_day_" + dayNumber, "id", getPackageName());

            TextView statusText = findViewById(statusResId);
            MaterialButton claimBtn = findViewById(btnResId);
            View card = findViewById(cardResId);

            if (claimed) {
                statusText.setText("Reclamato");
                statusText.setTextColor(getResources().getColor(R.color.status_connected));
                claimBtn.setVisibility(View.GONE);
                if (card != null) card.setBackgroundColor(getResources().getColor(R.color.surface_card));
            } else if (available) {
                statusText.setText("Da ritirare");
                statusText.setTextColor(getResources().getColor(R.color.status_connecting));
                claimBtn.setVisibility(View.VISIBLE);
                if (card != null) card.setBackgroundColor(getResources().getColor(R.color.surface_card));
            } else {
                statusText.setText("Bloccato");
                statusText.setTextColor(getResources().getColor(R.color.on_surface_dim));
                claimBtn.setVisibility(View.GONE);
                if (card != null) card.setBackgroundColor(getResources().getColor(R.color.surface_container));
            }
        });
    }

    private void loadTransactions() {
        executor.execute(() -> {
            try {
                String token = mAuth.getAccessToken();
                URL url = new URL(baseUrl + "/user/mevacoins/transactions");
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestProperty("Authorization", "Bearer " + token);
                conn.setConnectTimeout(5000);
                BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                StringBuilder resp = new StringBuilder();
                String line;
                while ((line = reader.readLine()) != null) resp.append(line);
                reader.close();
                conn.disconnect();

                JSONArray arr = new JSONArray(resp.toString());
                mainHandler.post(() -> {
                    transactionsContainer.removeAllViews();
                    if (arr.length() == 0) {
                        transactionsContainer.addView(transactionsEmpty);
                        return;
                    }
                    for (int i = 0; i < arr.length(); i++) {
                        try {
                            JSONObject tx = arr.getJSONObject(i);
                            int amount = tx.optInt("amount", 0);
                            String reason = tx.optString("reason", "");
                            String createdAt = tx.optString("created_at", "");

                            View item = getLayoutInflater().inflate(R.layout.item_transaction, transactionsContainer, false);
                            TextView amountText = item.findViewById(R.id.tx_amount);
                            TextView reasonText = item.findViewById(R.id.tx_reason);
                            TextView dateText = item.findViewById(R.id.tx_date);

                            amountText.setText((amount >= 0 ? "+" : "") + amount + " MVC");
                            amountText.setTextColor(amount >= 0
                                    ? getResources().getColor(R.color.status_connected)
                                    : getResources().getColor(R.color.error));

                            reasonText.setText(formatReason(reason));
                            dateText.setText(formatDate(createdAt));

                            transactionsContainer.addView(item);
                        } catch (Exception ignored) {}
                    }
                });
            } catch (Exception ignored) {}
        });
    }

    private String formatReason(String reason) {
        switch (reason) {
            case "checkin_giornaliero": return "Check-in giornaliero";
            case "bonus_nuovo_utente_giorno_1": return "Bonus nuovo utente - Giorno 1";
            case "bonus_nuovo_utente_giorno_2": return "Bonus nuovo utente - Giorno 2";
            case "bonus_nuovo_utente_giorno_3": return "Bonus nuovo utente - Giorno 3";
            case "bonus_nuovo_utente_giorno_4": return "Bonus nuovo utente - Giorno 4";
            case "admob_rewarded": return "Video rewarded";
            default: return reason.replace("_", " ");
        }
    }

    private String formatDate(String isoDate) {
        if (isoDate == null || isoDate.isEmpty()) return "";
        try {
            SimpleDateFormat in = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US);
            SimpleDateFormat out = new SimpleDateFormat("dd/MM/yyyy HH:mm", Locale.getDefault());
            return out.format(in.parse(isoDate.replaceAll("Z$", "").replaceAll("\\.[0-9]+", "")));
        } catch (Exception e) {
            return isoDate.length() > 10 ? isoDate.substring(0, 10) : isoDate;
        }
    }

    private void updateRewardedButton() {
        ChatApplication app = (ChatApplication) getApplication();
        AdManager adManager = app.getAdManager();
        if (adManager.isRewardedReady()) {
            btnWatchAd.setEnabled(true);
            btnWatchAd.setText("Guarda video +5 MVC");
        } else {
            btnWatchAd.setEnabled(false);
            btnWatchAd.setText("Video non disponibile");
        }
    }

    private void showRewardedAd() {
        ChatApplication app = (ChatApplication) getApplication();
        AdManager adManager = app.getAdManager();

        btnWatchAd.setEnabled(false);
        btnWatchAd.setText("Caricamento...");

        adManager.showRewarded(this, new AdManager.RewardedCallback() {
            @Override
            public void onRewardEarned(int amount) {
                // Credit MVC via backend API
                creditReward(amount > 0 ? amount : 5);
            }

            @Override
            public void onRewardedFailed() {
                mainHandler.post(() -> {
                    updateRewardedButton();
                    Snackbar.make(findViewById(android.R.id.content), "Video non disponibile", Snackbar.LENGTH_SHORT).show();
                });
            }
        });
    }

    private void creditReward(int amount) {
        executor.execute(() -> {
            try {
                String token = mAuth.getAccessToken();
                URL url = new URL(baseUrl + "/user/mevacoins/share");
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("POST");
                conn.setDoOutput(true);
                conn.setRequestProperty("Authorization", "Bearer " + token);
                conn.setRequestProperty("Content-Type", "application/json");
                conn.setConnectTimeout(5000);

                JSONObject body = new JSONObject();
                body.put("platform", "admob_rewarded");
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
                boolean success = result.optBoolean("success", false);
                int earned = result.optInt("earned", amount);

                mainHandler.post(() -> {
                    if (success) {
                        Snackbar.make(findViewById(android.R.id.content), "+" + earned + " MVC!", Snackbar.LENGTH_SHORT).show();
                        loadBalance();
                        loadTransactions();
                    } else {
                        Snackbar.make(findViewById(android.R.id.content), "Errore credito MVC", Snackbar.LENGTH_SHORT).show();
                    }
                    updateRewardedButton();
                });
            } catch (Exception e) {
                mainHandler.post(() -> {
                    updateRewardedButton();
                    Snackbar.make(findViewById(android.R.id.content), "Errore: " + e.getMessage(), Snackbar.LENGTH_SHORT).show();
                });
            }
        });
    }

    private void doCheckin() {
        btnCheckin.setEnabled(false);
        btnCheckin.setText("...");
        executor.execute(() -> {
            try {
                String token = mAuth.getAccessToken();
                URL url = new URL(baseUrl + "/user/mevacoins/checkin");
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("POST");
                conn.setDoOutput(true);
                conn.setRequestProperty("Authorization", "Bearer " + token);
                conn.setRequestProperty("Content-Type", "application/json");
                conn.setConnectTimeout(5000);

                OutputStream os = conn.getOutputStream();
                os.write("{}".getBytes());
                os.close();

                BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                StringBuilder resp = new StringBuilder();
                String line;
                while ((line = reader.readLine()) != null) resp.append(line);
                reader.close();
                conn.disconnect();

                JSONObject result = new JSONObject(resp.toString());
                boolean alreadyChecked = result.optBoolean("already_checked", false);

                mainHandler.post(() -> {
                    if (alreadyChecked) {
                        checkinStatusText.setText("Hai già fatto check-in oggi!");
                        checkinStatusText.setTextColor(getResources().getColor(R.color.status_connected));
                        btnCheckin.setText("Fatto");
                        btnCheckin.setEnabled(false);
                        Snackbar.make(findViewById(android.R.id.content), "Già registrato oggi!", Snackbar.LENGTH_SHORT).show();
                    } else {
                        int earned = result.optInt("earned", 15);
                        checkinStatusText.setText("Check-in effettuato! +" + earned + " MVC");
                        checkinStatusText.setTextColor(getResources().getColor(R.color.status_connected));
                        btnCheckin.setText("Riscosso");
                        btnCheckin.setEnabled(false);
                        loadBalance();
                        loadTransactions();
                        Snackbar.make(findViewById(android.R.id.content), "+" + earned + " MVC!", Snackbar.LENGTH_SHORT).show();
                    }
                });
            } catch (Exception e) {
                mainHandler.post(() -> {
                    btnCheckin.setText("Check-in");
                    btnCheckin.setEnabled(true);
                    Snackbar.make(findViewById(android.R.id.content), "Errore: " + e.getMessage(), Snackbar.LENGTH_SHORT).show();
                });
            }
        });
    }

    private void claimBonus(int dayNumber) {
        int btnResId = getResources().getIdentifier("btn_claim_bonus_" + dayNumber, "id", getPackageName());
        MaterialButton btn = findViewById(btnResId);
        btn.setEnabled(false);
        btn.setText("...");

        executor.execute(() -> {
            try {
                String token = mAuth.getAccessToken();
                URL url = new URL(baseUrl + "/user/mevacoins/new-user-bonus/claim");
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("POST");
                conn.setDoOutput(true);
                conn.setRequestProperty("Authorization", "Bearer " + token);
                conn.setRequestProperty("Content-Type", "application/json");
                conn.setConnectTimeout(5000);

                JSONObject body = new JSONObject();
                body.put("day", dayNumber);
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
                boolean claimed = result.optBoolean("claimed", false);

                mainHandler.post(() -> {
                    if (claimed) {
                        Snackbar.make(findViewById(android.R.id.content), "+30 MVC (Giorno " + dayNumber + ")", Snackbar.LENGTH_SHORT).show();
                        loadBalance();
                        loadBonusStatus();
                        loadTransactions();
                    } else {
                        btn.setEnabled(true);
                        btn.setText("Riscuoti");
                        Snackbar.make(findViewById(android.R.id.content), "Non disponibile", Snackbar.LENGTH_SHORT).show();
                    }
                });
            } catch (Exception e) {
                mainHandler.post(() -> {
                    btn.setEnabled(true);
                    btn.setText("Riscuoti");
                    Snackbar.make(findViewById(android.R.id.content), "Errore: " + e.getMessage(), Snackbar.LENGTH_SHORT).show();
                });
            }
        });
    }

    public void onBackClick(View v) {
        finish();
    }
}
