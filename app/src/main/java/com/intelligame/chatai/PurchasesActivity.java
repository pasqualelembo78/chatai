package com.intelligame.chatai;

import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;

import com.google.android.material.button.MaterialButton;
import com.google.android.material.card.MaterialCardView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class PurchasesActivity extends AppCompatActivity {

    private ChatApplication app;
    private AuthManager mAuth;
    private String baseUrl;
    private int rollbackFee = 20;

    private LinearLayout container;
    private TextView emptyView;
    private final List<JSONObject> purchases = new ArrayList<>();
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_purchases);

        app = (ChatApplication) getApplication();
        mAuth = app.getAuthManager();
        baseUrl = app.getPrefs().getServerUrl().replace("/chat", "");

        container = findViewById(R.id.purchases_container);
        emptyView = findViewById(R.id.purchases_empty);

        loadPurchases();
    }

    public void onBackClick(View v) {
        finish();
    }

    private void loadPurchases() {
        executor.execute(() -> {
            try {
                AuthManager.HttpResponse resp =
                        mAuth.requestWithRefresh(baseUrl + "/user/mevacoins/purchases", "GET", null, 8000);
                if (resp == null || resp.statusCode != 200) {
                    showError("Errore caricamento acquisti");
                    return;
                }
                JSONObject obj = new JSONObject(resp.body);
                rollbackFee = obj.optInt("rollback_fee", 20);
                JSONArray arr = obj.optJSONArray("purchases");
                purchases.clear();
                if (arr != null) {
                    for (int i = 0; i < arr.length(); i++) purchases.add(arr.getJSONObject(i));
                }
                mainHandler.post(this::renderList);
            } catch (Exception e) {
                showError("Errore caricamento acquisti");
            }
        });
    }

    private void showError(String msg) {
        mainHandler.post(() -> Toast.makeText(this, msg, Toast.LENGTH_SHORT).show());
    }

    private void renderList() {
        container.removeAllViews();
        if (purchases.isEmpty()) {
            emptyView.setVisibility(View.VISIBLE);
            return;
        }
        emptyView.setVisibility(View.GONE);
        for (JSONObject p : purchases) {
            container.addView(buildPurchaseCard(p));
        }
    }

    private View buildPurchaseCard(JSONObject p) {
        MaterialCardView card = new MaterialCardView(this);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, 0, 0, 16);
        card.setLayoutParams(lp);
        card.setCardBackgroundColor(getResources().getColor(R.color.surface));
        card.setRadius(16);
        card.setUseCompatPadding(true);

        LinearLayout inner = new LinearLayout(this);
        inner.setOrientation(LinearLayout.VERTICAL);
        inner.setPadding(20, 20, 20, 20);

        TextView name = new TextView(this);
        name.setText(p.optString("name", "Acquisto"));
        name.setTextColor(getResources().getColor(R.color.on_surface));
        name.setTextSize(16);
        name.setTypeface(null, android.graphics.Typeface.BOLD);
        inner.addView(name);

        String type = p.optString("type", "");
        String typeLabel = type.equals("feature") ? "Sblocco funzione"
                : type.equals("category") ? "Sblocco categoria"
                : "Consumabile" + (p.optInt("quantity", 1) > 1 ? " x" + p.optInt("quantity", 1) : "");
        TextView sub = new TextView(this);
        sub.setText(typeLabel + " - costo " + p.optInt("cost", 0) + " MVC");
        sub.setTextColor(getResources().getColor(R.color.on_surface_variant));
        sub.setTextSize(13);
        inner.addView(sub);

        MaterialButton btn = new MaterialButton(this);
        btn.setText("Rollback (-" + rollbackFee + " MVC)");
        btn.setBackgroundColor(getResources().getColor(R.color.primary));
        btn.setTextColor(getResources().getColor(R.color.on_primary));
        btn.setAllCaps(false);
        LinearLayout.LayoutParams blp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        blp.setMargins(0, 16, 0, 0);
        btn.setLayoutParams(blp);
        String pid = p.optString("purchase_id", "");
        btn.setOnClickListener(v -> confirmRollback(pid, p.optString("name", "acquisto"),
                p.optInt("cost", 0)));
        inner.addView(btn);

        card.addView(inner);
        return card;
    }

    private void confirmRollback(String purchaseId, String name, int cost) {
        int refund = Math.max(0, cost - rollbackFee);
        new AlertDialog.Builder(this)
                .setTitle("Conferma rollback")
                .setMessage("Annullare l'acquisto \"" + name + "\"?\n\n"
                        + "Tariffa rollback: " + rollbackFee + " MVC\n"
                        + "Rimborso: " + refund + " MVC\n\n"
                        + "I MVC tornano disponibili e l'acquisto viene annullato.")
                .setPositiveButton("Rollback", (d, w) -> doRollback(purchaseId))
                .setNegativeButton("Annulla", null)
                .show();
    }

    private void doRollback(String purchaseId) {
        executor.execute(() -> {
            try {
                JSONObject body = new JSONObject();
                body.put("purchase_id", purchaseId);
                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(
                        baseUrl + "/user/mevacoins/rollback", "POST", body.toString(), 10000);
                if (resp == null) {
                    showError("Errore di rete");
                    return;
                }
                if (resp.statusCode == 200) {
                    JSONObject obj = new JSONObject(resp.body);
                    int refund = obj.optInt("refund", 0);
                    mainHandler.post(() -> {
                        Toast.makeText(this, "Rollback effettuato. Rimborso: " + refund + " MVC", Toast.LENGTH_LONG).show();
                        loadPurchases();
                    });
                } else {
                    String err = "rollback non riuscito";
                    try {
                        JSONObject e = new JSONObject(resp.body);
                        err = e.optString("detail", err);
                    } catch (Exception ignored) {}
                    showError(err);
                }
            } catch (Exception e) {
                showError("Errore durante il rollback");
            }
        });
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        executor.shutdown();
    }
}
