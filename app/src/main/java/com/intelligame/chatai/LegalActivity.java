package com.intelligame.chatai;

import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.ImageButton;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.activity.OnBackPressedCallback;
import androidx.appcompat.app.AppCompatActivity;

import com.google.android.material.button.MaterialButton;

public class LegalActivity extends AppCompatActivity {

    public static final String EXTRA_DOC = "extra_doc";

    private static class LegalDoc {
        final String key;
        final int titleRes;
        final int rawRes;

        LegalDoc(String key, int titleRes, int rawRes) {
            this.key = key;
            this.titleRes = titleRes;
            this.rawRes = rawRes;
        }
    }

    private static final LegalDoc[] DOCS = new LegalDoc[]{
            new LegalDoc("privacy", R.string.legal_privacy_title, R.raw.legal_privacy),
            new LegalDoc("gdpr", R.string.legal_gdpr_title, R.raw.legal_gdpr),
            new LegalDoc("terms", R.string.legal_terms_title, R.raw.legal_terms),
            new LegalDoc("ads", R.string.legal_ads_title, R.raw.legal_ads),
    };

    private ScrollView listContainer;
    private LinearLayout list;
    private WebView webView;
    private TextView titleText;
    private ImageButton backBtn;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_legal);

        // Handle back press with OnBackPressedCallback (replaces deprecated onBackPressed)
        getOnBackPressedDispatcher().addCallback(this, new androidx.activity.OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
                if (webView.getVisibility() == View.VISIBLE) {
                    showList();
                } else {
                    finish();
                }
            }
        });

        titleText = findViewById(R.id.legal_title);
        backBtn = findViewById(R.id.legal_back);
        listContainer = findViewById(R.id.legal_list_container);
        list = findViewById(R.id.legal_list);
        webView = findViewById(R.id.legal_webview);

        int bg = getColor(R.color.background);
        int fg = getColor(R.color.on_surface);
        webView.setBackgroundColor(bg);
        webView.getSettings().setJavaScriptEnabled(false);
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                if (url != null && url.startsWith("legal:")) {
                    showDoc(url.substring("legal:".length()));
                    return true;
                }
                if (url != null && (url.startsWith("http://") || url.startsWith("https://"))) {
                    startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
                    return true;
                }
                return false;
            }
        });

        backBtn.setOnClickListener(v -> {
            if (webView.getVisibility() == View.VISIBLE) {
                showList();
            } else {
                finish();
            }
        });

        buildList();

        String extra = getIntent().getStringExtra(EXTRA_DOC);
        if (extra != null) {
            showDoc(extra);
        } else {
            showList();
        }
    }

    private void buildList() {
        list.removeAllViews();
        for (LegalDoc doc : DOCS) {
            MaterialButton btn = new MaterialButton(this);
            btn.setText(doc.titleRes);
            btn.setGravity(Gravity.START | Gravity.CENTER_VERTICAL);
            btn.setAllCaps(false);
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT);
            lp.bottomMargin = (int) (12 * getResources().getDisplayMetrics().density);
            btn.setLayoutParams(lp);
            final String key = doc.key;
            btn.setOnClickListener(v -> showDoc(key));
            list.addView(btn);
        }
    }

    private void showList() {
        webView.setVisibility(View.GONE);
        listContainer.setVisibility(View.VISIBLE);
        titleText.setText(R.string.legal_title);
    }

    private void showDoc(String key) {
        LegalDoc target = null;
        for (LegalDoc doc : DOCS) {
            if (doc.key.equals(key)) {
                target = doc;
                break;
            }
        }
        if (target == null) {
            showList();
            return;
        }
        String html = readRawText(target.rawRes);
        String css = "<style>"
                + "body{background:" + toHex(getColor(R.color.background))
                + ";color:" + toHex(getColor(R.color.on_surface))
                + ";font-family:sans-serif;line-height:1.5;padding:16px;}"
                + "h1{color:" + toHex(getColor(R.color.primary)) + ";}"
                + "h2{color:" + toHex(getColor(R.color.on_surface)) + ";margin-top:20px;}"
                + "a{color:" + toHex(getColor(R.color.primary)) + ";}"
                + "</style>";
        webView.loadDataWithBaseURL(null, css + html, "text/html", "utf-8", null);
        listContainer.setVisibility(View.GONE);
        webView.setVisibility(View.VISIBLE);
        titleText.setText(target.titleRes);
    }

    private static String toHex(int color) {
        return String.format("#%06X", (0xFFFFFF & color));
    }

private String readRawText(int resId) {
        try (java.io.InputStream is = getResources().openRawResource(resId);
             java.io.BufferedReader reader = new java.io.BufferedReader(
                     new java.io.InputStreamReader(is, java.nio.charset.StandardCharsets.UTF_8))) {
            StringBuilder sb = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) {
                sb.append(line).append('\n');
            }
            return sb.toString();
        } catch (Exception e) {
            return "<p>Errore di caricamento.</p>";
        }
    }
}
