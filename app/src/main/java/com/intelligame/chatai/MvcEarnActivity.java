package com.intelligame.chatai;

import android.graphics.Typeface;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.widget.GridLayout;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.annotation.Nullable;
import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;

import com.google.android.material.button.MaterialButton;
import com.google.android.material.snackbar.Snackbar;

import org.json.JSONArray;
import org.json.JSONObject;

import java.text.SimpleDateFormat;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MvcEarnActivity extends AppCompatActivity {

    private TextView balanceText;
    private TextView checkinStatusText;
    private MaterialButton btnCheckin;
    private MaterialButton btnWatchAd;
    private LinearLayout transactionsContainer;
    private TextView transactionsEmpty;
    private GridLayout streakGrid;

    private MaterialButton btnUnlockCategories;
    private MaterialButton btnUnlockImageGen;
    private MaterialButton btnUnlockVideoGen;
    private MaterialButton btnUnlockPremiumVoice;
    private MaterialButton btnUnlockExtendedMemory;

    private int currentBalance = 0;
    private java.util.Set<String> unlockedFeatures = new java.util.HashSet<>();

    private String baseUrl;
    private AuthManager mAuth;
    private ExecutorService executor = new SafeExecutor();
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
        streakGrid = findViewById(R.id.streak_grid);

        btnUnlockCategories = findViewById(R.id.btn_unlock_categories);
        btnUnlockImageGen = findViewById(R.id.btn_unlock_image_gen);
        btnUnlockVideoGen = findViewById(R.id.btn_unlock_video_gen);
        btnUnlockPremiumVoice = findViewById(R.id.btn_unlock_premium_voice);
        btnUnlockExtendedMemory = findViewById(R.id.btn_unlock_extended_memory);

        btnCheckin.setOnClickListener(v -> doCheckin());
        btnWatchAd.setOnClickListener(v -> showRewardedAd());
        updateRewardedButton();

        app.getAdManager().setRewardedReadyListener(() ->
                mainHandler.post(MvcEarnActivity.this::updateRewardedButton));

        btnUnlockCategories.setOnClickListener(v -> showCategoryDialog());
        btnUnlockImageGen.setOnClickListener(v -> attemptUnlockFeature("image_gen", 50, "Generazione Immagini"));
        btnUnlockVideoGen.setOnClickListener(v -> attemptUnlockFeature("video_gen", 100, "Generazione Video"));
        btnUnlockPremiumVoice.setOnClickListener(v -> attemptUnlockFeature("premium_voice", 30, "Messaggi Vocali Premium"));
        btnUnlockExtendedMemory.setOnClickListener(v -> attemptUnlockFeature("extended_memory", 80, "Memoria Estesa"));

        populateStreakGrid();
        loadAllData();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        ((ChatApplication) getApplication()).getAdManager().setRewardedReadyListener(null);
        if (executor != null) executor.shutdownNow();
    }

    private static int calculateReward(int day) {
        if (day == 30) return 100;
        return Math.min(10 + (day - 1) * 2, 100);
    }

    private void loadAllData() {
        loadBalance();
        loadBonusStatus();
        loadTransactions();
        loadUnlockStatus();
    }

    private void loadBalance() {
        executor.execute(() -> {
            try {
                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(baseUrl + "/user/mevacoins", "GET", null, 5000);
                JSONObject obj = new JSONObject(resp.body);
                int balance = obj.optInt("balance", 0);
                currentBalance = balance;
                mainHandler.post(() -> balanceText.setText(String.valueOf(balance)));
            } catch (Exception e) {
                mainHandler.post(() -> Snackbar.make(findViewById(android.R.id.content),
                        "Errore caricamento saldo", Snackbar.LENGTH_SHORT).show());
            }
        });
    }

    private void loadBonusStatus() {
        executor.execute(() -> {
            try {
                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(baseUrl + "/user/mevacoins/streak", "GET", null, 5000);

                if (resp.statusCode == 404) {
                    mainHandler.post(() -> {
                        checkinStatusText.setText("Sistema streak non ancora disponibile");
                        btnCheckin.setText("Check-in +15 MVC");
                    });
                    return;
                }

                JSONObject data = new JSONObject(resp.body);
                int currentDay = data.optInt("current_day", 1);
                boolean todayClaimed = data.optBoolean("already_claimed_today", false);
                JSONArray days = data.optJSONArray("days");
                if (days == null) {
                    days = new JSONArray();
                }

                int todayReward = calculateReward(currentDay);
                for (int i = 0; i < days.length(); i++) {
                    JSONObject day = days.getJSONObject(i);
                    int dayNumber = day.optInt("day", i + 1);
                    String status = day.optString("status", "locked");
                    if (dayNumber == currentDay && !todayClaimed) {
                        status = "available";
                    }
                    int reward = day.optInt("reward", calculateReward(dayNumber));
                    updateBonusDayUI(dayNumber, status, reward);
                }

                final boolean claimed = todayClaimed;
                final int reward = todayReward;
                final int day = currentDay;
                mainHandler.post(() -> {
                    if (claimed) {
                        checkinStatusText.setText("Hai già fatto check-in oggi!");
                        checkinStatusText.setTextColor(getResources().getColor(R.color.status_connected));
                        btnCheckin.setText("\u2713 Riscosso! +" + reward + " MVC");
                        btnCheckin.setEnabled(false);
                    } else {
                        checkinStatusText.setText("Giorno " + day + " - Prossima ricompensa:");
                        btnCheckin.setText("Check-in +" + reward + " MVC");
                        btnCheckin.setEnabled(true);
                    }
                });
            } catch (Exception e) {
                mainHandler.post(() -> {
                    btnCheckin.setText("Check-in +15 MVC");
                    Snackbar.make(findViewById(android.R.id.content),
                            "Errore caricamento streak", Snackbar.LENGTH_SHORT).show();
                });
            }
        });
    }

    private void populateStreakGrid() {
        streakGrid.removeAllViews();
        int cellWidth = (int) TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, 60, getResources().getDisplayMetrics());
        int cellHeight = (int) TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, 70, getResources().getDisplayMetrics());

        for (int day = 1; day <= 30; day++) {
            LinearLayout card = new LinearLayout(this);
            card.setOrientation(LinearLayout.VERTICAL);
            card.setGravity(Gravity.CENTER);
            card.setBackgroundResource(R.color.surface_card);
            card.setPadding(4, 4, 4, 4);

            GridLayout.LayoutParams params = new GridLayout.LayoutParams();
            params.width = cellWidth;
            params.height = cellHeight;
            params.setMargins(3, 3, 3, 3);
            card.setLayoutParams(params);

            TextView dayLabel = new TextView(this);
            dayLabel.setText("G" + day);
            dayLabel.setTextSize(TypedValue.COMPLEX_UNIT_SP, 11);
            dayLabel.setTextColor(getResources().getColor(R.color.on_surface_dim));
            dayLabel.setGravity(Gravity.CENTER);
            dayLabel.setTag("day_label_" + day);
            card.addView(dayLabel);

            TextView rewardText = new TextView(this);
            rewardText.setText("+" + calculateReward(day));
            rewardText.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13);
            rewardText.setTextColor(getResources().getColor(R.color.on_surface));
            rewardText.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
            rewardText.setGravity(Gravity.CENTER);
            rewardText.setTag("day_reward_" + day);
            card.addView(rewardText);

            TextView statusIcon = new TextView(this);
            statusIcon.setText("");
            statusIcon.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
            statusIcon.setGravity(Gravity.CENTER);
            statusIcon.setTag("day_status_" + day);
            card.addView(statusIcon);

            card.setTag("streak_card_" + day);
            streakGrid.addView(card);
        }
    }

    private void updateBonusDayUI(int dayNumber, String status) {
        updateBonusDayUI(dayNumber, status, calculateReward(dayNumber));
    }

    private void updateBonusDayUI(int dayNumber, String status, int reward) {
        mainHandler.post(() -> {
            LinearLayout card = streakGrid.findViewWithTag("streak_card_" + dayNumber);
            if (card == null) return;

            TextView rewardView = card.findViewWithTag("day_reward_" + dayNumber);
            if (rewardView != null) {
                rewardView.setText("+" + reward);
            }

            TextView statusIcon = card.findViewWithTag("day_status_" + dayNumber);
            if (statusIcon == null) return;

            switch (status) {
                case "claimed":
                    statusIcon.setText("\u2713");
                    statusIcon.setTextColor(getResources().getColor(R.color.status_connected));
                    card.setBackgroundResource(R.color.surface_container);
                    card.setOnClickListener(null);
                    break;
                case "available":
                    statusIcon.setText("\u25CB");
                    statusIcon.setTextColor(getResources().getColor(R.color.status_connecting));
                    card.setBackgroundResource(R.color.surface_card);
                    card.setOnClickListener(v -> claimBonus(dayNumber));
                    break;
                case "locked":
                default:
                    statusIcon.setText("\uD83D\uDD12");
                    statusIcon.setTextColor(getResources().getColor(R.color.on_surface_dim));
                    card.setBackgroundResource(R.color.surface_container);
                    card.setOnClickListener(null);
                    break;
            }
        });
    }

    private void claimBonus(int dayNumber) {
        int reward = calculateReward(dayNumber);
        runWithRewardedAd(() -> performBonusClaim(dayNumber, reward), "Video non disponibile");
    }

    private void performBonusClaim(int dayNumber, int reward) {
        executor.execute(() -> {
            try {
                JSONObject body = new JSONObject();
                body.put("day", dayNumber);
                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(baseUrl + "/user/mevacoins/streak/claim", "POST", body.toString(), 5000);

                if (resp.statusCode == 404) {
                    mainHandler.post(() -> Snackbar.make(findViewById(android.R.id.content),
                            "Sistema streak non ancora disponibile", Snackbar.LENGTH_SHORT).show());
                    return;
                }

                JSONObject result = new JSONObject(resp.body);
                boolean claimed = result.optBoolean("success", false);
                int earned = result.optInt("earned", reward);

                mainHandler.post(() -> {
                    if (claimed) {
                        Snackbar.make(findViewById(android.R.id.content),
                                "+" + earned + " MVC (Giorno " + dayNumber + ")", Snackbar.LENGTH_SHORT).show();
                        loadBalance();
                        loadBonusStatus();
                        loadTransactions();
                    } else {
                        Snackbar.make(findViewById(android.R.id.content),
                                "Non disponibile", Snackbar.LENGTH_SHORT).show();
                    }
                });
            } catch (Exception e) {
                mainHandler.post(() -> Snackbar.make(findViewById(android.R.id.content),
                        "Errore: " + e.getMessage(), Snackbar.LENGTH_SHORT).show());
            }
        });
    }

    private void loadTransactions() {
        executor.execute(() -> {
            try {
                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(baseUrl + "/user/mevacoins/transactions", "GET", null, 5000);

                JSONArray arr = new JSONArray(resp.body);
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
            } catch (Exception e) {
                mainHandler.post(() -> Snackbar.make(findViewById(android.R.id.content),
                        "Errore caricamento transazioni", Snackbar.LENGTH_SHORT).show());
            }
        });
    }

    private String formatReason(String reason) {
        switch (reason) {
            case "checkin_giornaliero":
                return "Check-in giornaliero";
            case "admob_rewarded":
                return "Video rewarded";
            default:
                if (reason.startsWith("streak_giorno_")) {
                    try {
                        int dayNum = Integer.parseInt(reason.substring("streak_giorno_".length()));
                        if (dayNum == 30) return "Streak 30 giorni - SUPER BONUS";
                        return "Streak " + dayNum + " giorni (+" + calculateReward(dayNum) + " MVC)";
                    } catch (NumberFormatException e) {
                        break;
                    }
                }
                return reason.replace("_", " ");
        }
        return reason.replace("_", " ");
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
                creditReward(amount > 0 ? amount : 5);
            }

            @Override
            public void onRewardedFailed() {
                mainHandler.post(() -> {
                    updateRewardedButton();
                    Snackbar.make(findViewById(android.R.id.content),
                            "Video non disponibile", Snackbar.LENGTH_SHORT).show();
                });
            }
        });
    }

    private void creditReward(int amount) {
        executor.execute(() -> {
            try {
                JSONObject body = new JSONObject();
                body.put("platform", "admob_rewarded");
                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(baseUrl + "/user/mevacoins/share", "POST", body.toString(), 5000);

                JSONObject result = new JSONObject(resp.body);
                boolean success = result.optBoolean("success", false);
                int earned = result.optInt("earned", amount);

                mainHandler.post(() -> {
                    if (success) {
                        Snackbar.make(findViewById(android.R.id.content),
                                "+" + earned + " MVC!", Snackbar.LENGTH_SHORT).show();
                        loadBalance();
                        loadTransactions();
                    } else {
                        Snackbar.make(findViewById(android.R.id.content),
                                "Errore credito MVC", Snackbar.LENGTH_SHORT).show();
                    }
                    updateRewardedButton();
                });
            } catch (Exception e) {
                mainHandler.post(() -> {
                    updateRewardedButton();
                    Snackbar.make(findViewById(android.R.id.content),
                            "Errore: " + e.getMessage(), Snackbar.LENGTH_SHORT).show();
                });
            }
        });
    }

    private void loadUnlockStatus() {
        executor.execute(() -> {
            try {
                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(baseUrl + "/user/mevacoins/unlocks", "GET", null, 5000);
                JSONObject obj = new JSONObject(resp.body);
                JSONArray features = obj.optJSONArray("features");
                unlockedFeatures.clear();
                if (features != null) {
                    for (int i = 0; i < features.length(); i++) {
                        unlockedFeatures.add(features.getString(i));
                    }
                }
                JSONArray categories = obj.optJSONArray("categories");
                final java.util.List<String> unlockedCats = new java.util.ArrayList<>();
                if (categories != null) {
                    for (int i = 0; i < categories.length(); i++) {
                        unlockedCats.add(categories.getString(i));
                    }
                }
                mainHandler.post(() -> {
                    updateFeatureButtons();
                    btnUnlockCategories.setText(unlockedCats.isEmpty() ? "Vedi" : "Vedi (" + unlockedCats.size() + " sbloccate)");
                });
            } catch (Exception e) {
                mainHandler.post(() -> Snackbar.make(findViewById(android.R.id.content),
                        "Errore caricamento sblochi", Snackbar.LENGTH_SHORT).show());
            }
        });
    }

    private void updateFeatureButtons() {
        updateOneButton(btnUnlockImageGen, "image_gen", 50);
        updateOneButton(btnUnlockVideoGen, "video_gen", 100);
        updateOneButton(btnUnlockPremiumVoice, "premium_voice", 30);
        updateOneButton(btnUnlockExtendedMemory, "extended_memory", 80);
    }

    private void updateOneButton(MaterialButton btn, String featureId, int cost) {
        if (unlockedFeatures.contains(featureId)) {
            btn.setText("✓ Sbloccato");
            btn.setEnabled(false);
            btn.setBackgroundColor(0xFF4CAF50);
        } else {
            btn.setText(cost + " MVC");
            btn.setEnabled(true);
            btn.setBackgroundColor(getResources().getColor(R.color.primary));
        }
    }

    private void attemptUnlockFeature(String featureId, int cost, String featureName) {
        if (unlockedFeatures.contains(featureId)) {
            Snackbar.make(findViewById(android.R.id.content), featureName + " già sbloccata", Snackbar.LENGTH_SHORT).show();
            return;
        }
        if (currentBalance < cost) {
            Snackbar.make(findViewById(android.R.id.content),
                    "Saldo insufficiente. Servono " + cost + " MVC (hai " + currentBalance + ")",
                    Snackbar.LENGTH_LONG).show();
            return;
        }
        new AlertDialog.Builder(this)
                .setTitle("Sblocca " + featureName)
                .setMessage("Vuoi spendere " + cost + " MVC per sbloccare \"" + featureName + "\"?\n\nSaldo attuale: " + currentBalance + " MVC")
                .setPositiveButton("Sblocca (" + cost + " MVC)", (d, w) -> doUnlockFeature(featureId, cost, featureName))
                .setNegativeButton("Annulla", null)
                .show();
    }

    private void doUnlockFeature(String featureId, int cost, String featureName) {
        executor.execute(() -> {
            try {
                JSONObject body = new JSONObject();
                body.put("content_type", "feature");
                body.put("content_id", featureId);
                body.put("amount", cost);
                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(baseUrl + "/user/mevacoins/spend", "POST", body.toString(), 10000);

                if (resp.statusCode == 200) {
                    JSONObject result = new JSONObject(resp.body);
                    if (result.optBoolean("already_unlocked", false)) {
                        unlockedFeatures.add(featureId);
                        mainHandler.post(() -> {
                            updateFeatureButtons();
                            Snackbar.make(findViewById(android.R.id.content),
                                    featureName + " già sbloccata!", Snackbar.LENGTH_SHORT).show();
                        });
                        return;
                    }
                    unlockedFeatures.add(featureId);
                    mainHandler.post(() -> {
                        updateFeatureButtons();
                        loadBalance();
                        loadTransactions();
                        Snackbar.make(findViewById(android.R.id.content),
                                "✓ " + featureName + " sbloccata! -" + cost + " MVC", Snackbar.LENGTH_LONG).show();
                    });
                } else if (resp.statusCode == 400 && resp.body.contains("saldo")) {
                    mainHandler.post(() -> Snackbar.make(findViewById(android.R.id.content),
                            "Saldo insufficiente", Snackbar.LENGTH_SHORT).show());
                } else {
                    mainHandler.post(() -> Snackbar.make(findViewById(android.R.id.content),
                            "Errore: " + resp.body, Snackbar.LENGTH_LONG).show());
                }
            } catch (Exception e) {
                mainHandler.post(() -> Snackbar.make(findViewById(android.R.id.content),
                        "Errore: " + e.getMessage(), Snackbar.LENGTH_SHORT).show());
            }
        });
    }

    private void showCategoryDialog() {
        String[][] cats = {
                {"horror", "Horror", "200"},
                {"flirt", "Flirt", "300"},
                {"relazioni", "Relazioni", "300"},
                {"confessioni", "Confessioni", "300"},
                {"seduzione", "Seduzione", "500"}
        };
        StringBuilder msg = new StringBuilder("Scegli quale categoria sbloccare:\n\n");
        for (String[] c : cats) {
            msg.append(c[1]).append(" - ").append(c[2]).append(" MVC\n");
        }
        msg.append("\nSaldo attuale: ").append(currentBalance).append(" MVC");
        String[] items = new String[cats.length];
        for (int i = 0; i < cats.length; i++) {
            items[i] = cats[i][1] + " (" + cats[i][2] + " MVC)";
        }
        new AlertDialog.Builder(this)
                .setTitle("Sblocca Categorie Hot")
                .setMessage(msg.toString())
                .setItems(items, (d, which) -> {
                    String catId = cats[which][0];
                    String catName = cats[which][1];
                    int catCost = Integer.parseInt(cats[which][2]);
                    if (currentBalance < catCost) {
                        Snackbar.make(findViewById(android.R.id.content),
                                "Saldo insufficiente. Servono " + catCost + " MVC (hai " + currentBalance + ")",
                                Snackbar.LENGTH_LONG).show();
                        return;
                    }
                    new AlertDialog.Builder(this)
                            .setTitle("Sblocca " + catName)
                            .setMessage("Spendere " + catCost + " MVC per sbloccare la categoria \"" + catName + "\"?")
                            .setPositiveButton("Sblocca", (dd, ww) -> doUnlockCategory(catId, catCost, catName))
                            .setNegativeButton("Annulla", null)
                            .show();
                })
                .setNegativeButton("Chiudi", null)
                .show();
    }

    private void doUnlockCategory(String catId, int cost, String catName) {
        executor.execute(() -> {
            try {
                JSONObject body = new JSONObject();
                body.put("content_type", "category");
                body.put("content_id", catId);
                body.put("amount", cost);
                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(baseUrl + "/user/mevacoins/spend", "POST", body.toString(), 10000);

                if (resp.statusCode == 200) {
                    mainHandler.post(() -> {
                        loadBalance();
                        loadUnlockStatus();
                        loadTransactions();
                        Snackbar.make(findViewById(android.R.id.content),
                                "✓ " + catName + " sbloccata! -" + cost + " MVC", Snackbar.LENGTH_LONG).show();
                    });
                } else {
                    final String errMsg;
                    if (resp.statusCode == 400 && resp.body.contains("saldo")) {
                        errMsg = "Saldo insufficiente";
                    } else {
                        errMsg = "Errore: " + resp.body;
                    }
                    mainHandler.post(() -> Snackbar.make(findViewById(android.R.id.content),
                            errMsg, Snackbar.LENGTH_LONG).show());
                }
            } catch (Exception e) {
                mainHandler.post(() -> Snackbar.make(findViewById(android.R.id.content),
                        "Errore: " + e.getMessage(), Snackbar.LENGTH_SHORT).show());
            }
        });
    }

    private void doCheckin() {
        btnCheckin.setEnabled(false);
        btnCheckin.setText("Guarda il video...");
        runWithRewardedAd(this::performCheckinClaim, "Video non disponibile: check-in diretto");
    }

    private void performCheckinClaim() {
        executor.execute(() -> {
            try {
                JSONObject body = new JSONObject();
                body.put("day", 0);
                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(baseUrl + "/user/mevacoins/streak/claim", "POST", body.toString(), 10000);

                if (resp.statusCode < 200 || resp.statusCode >= 300) {
                    final String errMsg = resp.body != null && !resp.body.isEmpty() ? resp.body : "HTTP " + resp.statusCode;
                    mainHandler.post(() -> {
                        btnCheckin.setText("Check-in");
                        btnCheckin.setEnabled(true);
                        Snackbar.make(findViewById(android.R.id.content),
                                "Errore check-in: " + errMsg, Snackbar.LENGTH_LONG).show();
                    });
                    return;
                }

                JSONObject result = new JSONObject(resp.body);
                boolean success = result.optBoolean("success", false);
                final int earned = result.optInt("earned", 0);

                mainHandler.post(() -> {
                    if (success) {
                        checkinStatusText.setText("Check-in effettuato! +" + earned + " MVC");
                        checkinStatusText.setTextColor(getResources().getColor(R.color.status_connected));
                        btnCheckin.setText("\u2713 Riscosso! +" + earned + " MVC");
                        btnCheckin.setEnabled(false);
                        loadBalance();
                        loadBonusStatus();
                        loadTransactions();
                        Snackbar.make(findViewById(android.R.id.content),
                                "+" + earned + " MVC!", Snackbar.LENGTH_SHORT).show();
                    } else {
                        checkinStatusText.setText("Hai già fatto check-in oggi!");
                        checkinStatusText.setTextColor(getResources().getColor(R.color.status_connected));
                        btnCheckin.setText("\u2713 Riscosso");
                        btnCheckin.setEnabled(false);
                        Snackbar.make(findViewById(android.R.id.content),
                                "Già registrato oggi!", Snackbar.LENGTH_SHORT).show();
                    }
                });
            } catch (Exception e) {
                mainHandler.post(() -> {
                    btnCheckin.setText("Check-in");
                    btnCheckin.setEnabled(true);
                    Snackbar.make(findViewById(android.R.id.content),
                            "Errore: " + e.getMessage(), Snackbar.LENGTH_SHORT).show();
                });
            }
        });
    }

    /**
     * Mostra un video rewarded; alla fine (o se non disponibile) esegue l'azione di riscatto.
     * Fallback diretto se l'annuncio non è pronto, per non bloccare l'utente in assenza di fill.
     */
    private void runWithRewardedAd(Runnable onGranted, String fallbackMsg) {
        ChatApplication app = (ChatApplication) getApplication();
        AdManager adManager = app.getAdManager();
        if (!adManager.isRewardedReady()) {
            onGranted.run();
            return;
        }
        adManager.showRewarded(this, new AdManager.RewardedCallback() {
            @Override
            public void onRewardEarned(int amount) {
                onGranted.run();
            }

            @Override
            public void onRewardedFailed() {
                mainHandler.post(() -> Snackbar.make(findViewById(android.R.id.content),
                        fallbackMsg, Snackbar.LENGTH_SHORT).show());
                onGranted.run();
            }
        });
    }

    public void onBackClick(View v) {
        finish();
    }
}
