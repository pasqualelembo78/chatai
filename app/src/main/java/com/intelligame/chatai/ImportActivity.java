package com.intelligame.chatai;

import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.ImageButton;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.Spinner;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;

import com.google.android.material.button.MaterialButton;
import com.google.android.material.snackbar.Snackbar;
import com.google.android.material.textfield.TextInputEditText;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class ImportActivity extends AppCompatActivity {

    private LinearLayout sourcesContainer;
    private TextInputEditText fieldCount, fieldGenre, fieldAvatarLimit;
    private Spinner spinnerPreset;
    private MaterialButton btnImport, btnScanDuplicates, btnCleanDuplicates, btnGenerateAvatars;
    private ProgressBar progressBar;
    private TextView progressText, progressStats, resultTitle, resultDetails;
    private TextView duplicatesCount, duplicatesDetails;
    private LinearLayout progressSection, resultSection, duplicatesResult;

    private ProgressBar progressBarAvatar;
    private TextView progressTextAvatar, progressStatsAvatar, resultTitleAvatar, resultDetailsAvatar;
    private LinearLayout progressSectionAvatar, resultSectionAvatar;

    private String baseUrl;
    private String selectedSource = "charactercodex";
    private List<String> sourceIds = new ArrayList<>();

    private ExecutorService executor = new SafeExecutor();
    private Handler mainHandler = new Handler(Looper.getMainLooper());
    private boolean isImporting = false;
    private Runnable progressRunnable;

    private boolean isGeneratingAvatars = false;
    private Runnable avatarProgressRunnable;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_import);

        ChatApplication app = (ChatApplication) getApplication();
        PrefsManager prefs = app.getPrefs();
        baseUrl = prefs.getServerUrl().replace("/chat", "");

        // Init views
        ImageButton btnBack = findViewById(R.id.btn_back);
        sourcesContainer = findViewById(R.id.sources_container);
        fieldCount = findViewById(R.id.field_count);
        fieldGenre = findViewById(R.id.field_genre);
        spinnerPreset = findViewById(R.id.spinner_preset);
        btnImport = findViewById(R.id.btn_import);
        btnScanDuplicates = findViewById(R.id.btn_scan_duplicates);
        btnCleanDuplicates = findViewById(R.id.btn_clean_duplicates);
        progressBar = findViewById(R.id.progress_bar);
        progressText = findViewById(R.id.progress_text);
        progressStats = findViewById(R.id.progress_stats);
        resultTitle = findViewById(R.id.result_title);
        resultDetails = findViewById(R.id.result_details);
        duplicatesCount = findViewById(R.id.duplicates_count);
        duplicatesDetails = findViewById(R.id.duplicates_details);
        progressSection = findViewById(R.id.progress_section);
        resultSection = findViewById(R.id.result_section);
        duplicatesResult = findViewById(R.id.duplicates_result);

        fieldAvatarLimit = findViewById(R.id.field_avatar_limit);
        btnGenerateAvatars = findViewById(R.id.btn_generate_avatars);
        progressBarAvatar = findViewById(R.id.progress_bar_avatar);
        progressTextAvatar = findViewById(R.id.progress_text_avatar);
        progressStatsAvatar = findViewById(R.id.progress_stats_avatar);
        progressSectionAvatar = findViewById(R.id.progress_section_avatar);
        resultSectionAvatar = findViewById(R.id.result_section_avatar);
        resultTitleAvatar = findViewById(R.id.result_title_avatar);
        resultDetailsAvatar = findViewById(R.id.result_details_avatar);

        btnBack.setOnClickListener(v -> finish());
        btnImport.setOnClickListener(v -> startImport());
        btnScanDuplicates.setOnClickListener(v -> scanDuplicates());
        btnCleanDuplicates.setOnClickListener(v -> cleanDuplicates());
        btnGenerateAvatars.setOnClickListener(v -> generateAvatars());

        // Preset counts
        String[] presets = {"100", "500", "1000", "2000", "5000", "10000", "Tutti"};
        ArrayAdapter<String> presetAdapter = new ArrayAdapter<>(this,
                android.R.layout.simple_spinner_item, presets);
        presetAdapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        spinnerPreset.setAdapter(presetAdapter);
        spinnerPreset.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(android.widget.AdapterView<?> parent, View view, int position, long id) {
                if (position < 6) {
                    fieldCount.setText(presets[position]);
                } else {
                    fieldCount.setText("16000");
                }
            }
            @Override
            public void onNothingSelected(android.widget.AdapterView<?> parent) {}
        });

        loadSources();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (executor != null) executor.shutdownNow();
        mainHandler.removeCallbacksAndMessages(null);
    }

    private void loadSources() {
        executor.execute(() -> {
            try {
                String json = httpGet(baseUrl + "/admin/import/sources");
                if (json == null) return;

                JSONArray arr = new JSONArray(json);
                List<String> names = new ArrayList<>();
                sourceIds.clear();

                StringBuilder sb = new StringBuilder();
                for (int i = 0; i < arr.length(); i++) {
                    JSONObject obj = arr.getJSONObject(i);
                    String id = obj.getString("id");
                    String name = obj.getString("name");
                    String desc = obj.optString("description", "");
                    String icon = obj.optString("icon", "📦");
                    int estimated = obj.optInt("estimated_count", 0);
                    boolean isDefault = obj.optBoolean("default", false);

                    sourceIds.add(id);
                    names.add(icon + " " + name);

                    sb.append(id).append("|").append(name).append("|")
                      .append(desc).append("|").append(estimated).append("|")
                      .append(isDefault).append("\n");
                }

                final String sourcesData = sb.toString();
                mainHandler.post(() -> {
                    populateSources(sourcesData);
                    if (!names.isEmpty()) {
                        ArrayAdapter<String> adapter = new ArrayAdapter<>(
                            ImportActivity.this, android.R.layout.simple_spinner_item, names);
                        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
                    }
                });
            } catch (Exception e) {
                mainHandler.post(() -> Snackbar.make(findViewById(android.R.id.content),
                    "Errore caricamento sorgenti", Snackbar.LENGTH_SHORT).show());
            }
        });
    }

    private void populateSources(String data) {
        sourcesContainer.removeAllViews();
        String[] lines = data.trim().split("\n");

        for (String line : lines) {
            String[] parts = line.split("\\|", 5);
            if (parts.length < 5) continue;

            String id = parts[0];
            String name = parts[1];
            String desc = parts[2];
            int estimated = Integer.parseInt(parts[3]);
            boolean isDefault = Boolean.parseBoolean(parts[4]);

            View card = getLayoutInflater().inflate(R.layout.item_source_card, sourcesContainer, false);
            TextView tvName = card.findViewById(R.id.source_name);
            TextView tvDesc = card.findViewById(R.id.source_desc);
            TextView tvCount = card.findViewById(R.id.source_count);
            View indicator = card.findViewById(R.id.source_indicator);

            tvName.setText(name);
            tvDesc.setText(desc);
            tvCount.setText("~" + estimated + " personaggi");

            if (isDefault) {
                indicator.setVisibility(View.VISIBLE);
                selectedSource = id;
            } else {
                indicator.setVisibility(View.GONE);
            }

            card.setOnClickListener(v -> {
                selectedSource = id;
                for (int i = 0; i < sourcesContainer.getChildCount(); i++) {
                    View child = sourcesContainer.getChildAt(i);
                    View ind = child.findViewById(R.id.source_indicator);
                    ind.setVisibility(child == card ? View.VISIBLE : View.GONE);
                }
            });

            sourcesContainer.addView(card);
        }
    }

    private void startImport() {
        if (isImporting) return;

        String countStr = fieldCount.getText().toString().trim();
        int count = countStr.isEmpty() ? 500 : Integer.parseInt(countStr);
        String genreText = fieldGenre.getText().toString().trim();
        final String genre = genreText.isEmpty() ? null : genreText;

        isImporting = true;
        btnImport.setEnabled(false);
        btnImport.setText("Importazione in corso...");
        progressSection.setVisibility(View.VISIBLE);
        resultSection.setVisibility(View.GONE);
        progressBar.setProgress(0);
        progressText.setText("Avvio importazione...");

        executor.execute(() -> {
            try {
                JSONObject body = new JSONObject();
                body.put("source", selectedSource);
                body.put("count", count);
                if (genre != null) body.put("genre", genre);

                String response = httpPost(baseUrl + "/admin/import/start", body.toString());
                if (response == null) {
                    mainHandler.post(() -> {
                        isImporting = false;
                        btnImport.setEnabled(true);
                        btnImport.setText("Avvia Importazione");
                        Snackbar.make(findViewById(android.R.id.content),
                            "Errore: impossibile avviare l'importazione", Snackbar.LENGTH_LONG).show();
                    });
                    return;
                }

                // Start polling progress
                startProgressPolling();

            } catch (Exception e) {
                mainHandler.post(() -> {
                    isImporting = false;
                    btnImport.setEnabled(true);
                    btnImport.setText("Avvia Importazione");
                    Snackbar.make(findViewById(android.R.id.content),
                        "Errore: " + e.getMessage(), Snackbar.LENGTH_LONG).show();
                });
            }
        });
    }

    private void startProgressPolling() {
        progressRunnable = new Runnable() {
            @Override
            public void run() {
                if (!isImporting) return;

                executor.execute(() -> {
                    try {
                        String json = httpGet(baseUrl + "/admin/import/status");
                        if (json != null) {
                            JSONObject status = new JSONObject(json);
                            boolean running = status.optBoolean("running", false);
                            int progress = status.optInt("progress", 0);
                            int total = status.optInt("total", 0);
                            int imported = status.optInt("imported", 0);
                            int skipped = status.optInt("skipped", 0);
                            int errors = status.optInt("errors", 0);
                            String message = status.optString("message", "");

                            mainHandler.post(() -> {
                                if (total > 0) {
                                    int pct = (int) ((progress * 100.0) / total);
                                    progressBar.setProgress(pct);
                                }
                                progressText.setText(message);
                                progressStats.setText(String.format(
                                    "Progresso: %d/%d | Importati: %d | Saltati: %d | Errori: %d",
                                    progress, total, imported, skipped, errors));

                                if (!running) {
                                    isImporting = false;
                                    btnImport.setEnabled(true);
                                    btnImport.setText("Avvia Importazione");
                                    showResult(status);
                                } else {
                                    mainHandler.postDelayed(this, 1500);
                                }
                            });
                        } else {
                            mainHandler.postDelayed(this, 2000);
                        }
                    } catch (Exception e) {
                        mainHandler.postDelayed(this, 3000);
                    }
                });
            }
        };
        mainHandler.postDelayed(progressRunnable, 1000);
    }

    private void generateAvatars() {
        if (isGeneratingAvatars) return;

        String limitStr = fieldAvatarLimit.getText().toString().trim();
        int limit = limitStr.isEmpty() ? 50 : Integer.parseInt(limitStr);

        isGeneratingAvatars = true;
        btnGenerateAvatars.setEnabled(false);
        btnGenerateAvatars.setText("Generazione in corso...");
        progressSectionAvatar.setVisibility(View.VISIBLE);
        resultSectionAvatar.setVisibility(View.GONE);
        progressBarAvatar.setProgress(0);
        progressTextAvatar.setText("Avvio generazione avatar...");

        executor.execute(() -> {
            try {
                JSONObject body = new JSONObject();
                body.put("limit", limit);

                String response = httpPost(baseUrl + "/admin/avatars/generate", body.toString());
                if (response == null) {
                    mainHandler.post(() -> {
                        isGeneratingAvatars = false;
                        btnGenerateAvatars.setEnabled(true);
                        btnGenerateAvatars.setText("Genera Avatar (Bio + Scenario)");
                        Snackbar.make(findViewById(android.R.id.content),
                            "Errore: impossibile avviare la generazione", Snackbar.LENGTH_LONG).show();
                    });
                    return;
                }

                startAvatarPolling();

            } catch (Exception e) {
                mainHandler.post(() -> {
                    isGeneratingAvatars = false;
                    btnGenerateAvatars.setEnabled(true);
                    btnGenerateAvatars.setText("Genera Avatar (Bio + Scenario)");
                    Snackbar.make(findViewById(android.R.id.content),
                        "Errore: " + e.getMessage(), Snackbar.LENGTH_LONG).show();
                });
            }
        });
    }

    private void startAvatarPolling() {
        avatarProgressRunnable = new Runnable() {
            @Override
            public void run() {
                if (!isGeneratingAvatars) return;

                executor.execute(() -> {
                    try {
                        String json = httpGet(baseUrl + "/admin/avatars/status");
                        if (json != null) {
                            JSONObject status = new JSONObject(json);
                            boolean running = status.optBoolean("running", false);
                            int progress = status.optInt("progress", 0);
                            int total = status.optInt("total", 0);
                            int generated = status.optInt("generated", 0);
                            int bios = status.optInt("bios", 0);
                            int errors = status.optInt("errors", 0);
                            String message = status.optString("message", "");

                            mainHandler.post(() -> {
                                if (total > 0) {
                                    int pct = (int) ((progress * 100.0) / total);
                                    progressBarAvatar.setProgress(pct);
                                } else {
                                    progressBarAvatar.setIndeterminate(true);
                                }
                                progressTextAvatar.setText(message);
                                progressStatsAvatar.setText(String.format(
                                    "Avatar: %d/%d | Bio: %d | Errori: %d",
                                    generated, total, bios, errors));

                                if (!running) {
                                    isGeneratingAvatars = false;
                                    btnGenerateAvatars.setEnabled(true);
                                    btnGenerateAvatars.setText("Genera Avatar (Bio + Scenario)");
                                    progressBarAvatar.setIndeterminate(false);
                                    showAvatarResult(status);
                                } else {
                                    mainHandler.postDelayed(this, 2000);
                                }
                            });
                        } else {
                            mainHandler.postDelayed(this, 2000);
                        }
                    } catch (Exception e) {
                        mainHandler.postDelayed(this, 3000);
                    }
                });
            }
        };
        mainHandler.postDelayed(avatarProgressRunnable, 1000);
    }

    private void showAvatarResult(JSONObject status) {
        resultSectionAvatar.setVisibility(View.VISIBLE);
        int generated = status.optInt("generated", 0);
        int bios = status.optInt("bios", 0);
        int errors = status.optInt("errors", 0);

        if (generated > 0) {
            resultTitleAvatar.setText("✅ Avatar generati!");
            resultTitleAvatar.setTextColor(getResources().getColor(R.color.status_connected));
        } else {
            resultTitleAvatar.setText("Nessun avatar generato");
            resultTitleAvatar.setTextColor(getResources().getColor(R.color.status_warning));
        }

        StringBuilder details = new StringBuilder();
        details.append("Avatar: ").append(generated).append("\n");
        details.append("Biografie: ").append(bios).append("\n");
        details.append("Errori: ").append(errors);
        resultDetailsAvatar.setText(details.toString());
    }

    private void showResult(JSONObject status) {
        resultSection.setVisibility(View.VISIBLE);
        int imported = status.optInt("imported", 0);
        int skipped = status.optInt("skipped", 0);

        if (imported > 0) {
            resultTitle.setText("✅ Importazione completata!");
            resultTitle.setTextColor(getResources().getColor(R.color.status_connected));
            StringBuilder details = new StringBuilder();
            details.append("Importati: ").append(imported).append(" personaggi\n");
            details.append("Duplicati saltati: ").append(skipped).append("\n");

            JSONObject result = status.optJSONObject("result");
            if (result != null && result.has("categories")) {
                JSONObject cats = result.optJSONObject("categories");
                if (cats != null) {
                    details.append("\nCategorie:\n");
                    JSONArray keys = cats.names();
                    if (keys != null) {
                        for (int i = 0; i < keys.length(); i++) {
                            try {
                                String key = keys.getString(i);
                                int val = cats.getInt(key);
                                details.append("  • ").append(key).append(": ").append(val).append("\n");
                            } catch (Exception ignored) {}
                        }
                    }
                }
            }
            resultDetails.setText(details.toString());
        } else {
            resultTitle.setText("Nessun nuovo personaggio");
            resultTitle.setTextColor(getResources().getColor(R.color.status_warning));
            resultDetails.setText("Tutti i personaggi erano già presenti nel database.");
        }
    }

    private void scanDuplicates() {
        btnScanDuplicates.setEnabled(false);
        btnScanDuplicates.setText("Scansione in corso...");
        duplicatesResult.setVisibility(View.GONE);

        executor.execute(() -> {
            try {
                String json = httpGet(baseUrl + "/admin/duplicates");
                if (json == null) {
                    mainHandler.post(() -> {
                        btnScanDuplicates.setEnabled(true);
                        btnScanDuplicates.setText("Scansiona Duplicati");
                        Snackbar.make(findViewById(android.R.id.content),
                            "Errore durante la scansione", Snackbar.LENGTH_SHORT).show();
                    });
                    return;
                }

                JSONObject obj = new JSONObject(json);
                int total = obj.optInt("total_duplicates", 0);
                JSONArray dups = obj.optJSONArray("duplicates");

                StringBuilder details = new StringBuilder();
                if (dups != null) {
                    int idDups = 0, nameDups = 0;
                    for (int i = 0; i < dups.length(); i++) {
                        JSONObject dup = dups.getJSONObject(i);
                        String type = dup.optString("type", "");
                        if ("id".equals(type)) idDups++;
                        else nameDups++;
                    }
                    details.append("Duplicati per ID: ").append(idDups).append("\n");
                    details.append("Duplicati per nome: ").append(nameDups);
                }

                final String detailsStr = details.toString();
                mainHandler.post(() -> {
                    btnScanDuplicates.setEnabled(true);
                    btnScanDuplicates.setText("Scansiona Duplicati");
                    duplicatesResult.setVisibility(View.VISIBLE);
                    duplicatesCount.setText("Trovati " + total + " duplicati");
                    duplicatesCount.setTextColor(total > 0
                        ? getResources().getColor(R.color.error)
                        : getResources().getColor(R.color.status_connected));
                    duplicatesDetails.setText(detailsStr);
                    btnCleanDuplicates.setVisibility(total > 0 ? View.VISIBLE : View.GONE);
                });
            } catch (Exception e) {
                mainHandler.post(() -> {
                    btnScanDuplicates.setEnabled(true);
                    btnScanDuplicates.setText("Scansiona Duplicati");
                });
            }
        });
    }

    private void cleanDuplicates() {
        new androidx.appcompat.app.AlertDialog.Builder(this)
            .setTitle("Rimuovi duplicati?")
            .setMessage("Questa operazione rimuoverà tutti i personaggi duplicati dal database. Verrà mantenuta solo la prima occorrenza di ogni personaggio.")
            .setPositiveButton("Rimuovi", (dialog, which) -> executeClean())
            .setNegativeButton("Annulla", null)
            .show();
    }

    private void executeClean() {
        btnCleanDuplicates.setEnabled(false);
        btnCleanDuplicates.setText("Rimozione in corso...");

        executor.execute(() -> {
            try {
                JSONObject body = new JSONObject();
                String response = httpPost(baseUrl + "/admin/duplicates/clean", body.toString());
                if (response == null) {
                    mainHandler.post(() -> {
                        btnCleanDuplicates.setEnabled(true);
                        btnCleanDuplicates.setText("Rimuovi Duplicati");
                        Snackbar.make(findViewById(android.R.id.content),
                            "Errore durante la pulizia", Snackbar.LENGTH_SHORT).show();
                    });
                    return;
                }

                JSONObject result = new JSONObject(response);
                int removed = result.optInt("removed", 0);
                int remaining = result.optInt("remaining", 0);

                mainHandler.post(() -> {
                    btnCleanDuplicates.setEnabled(false);
                    btnCleanDuplicates.setText("Completato!");
                    duplicatesCount.setText("Rimossi " + removed + " duplicati");
                    duplicatesCount.setTextColor(getResources().getColor(R.color.status_connected));
                    duplicatesDetails.setText("Rimasti " + remaining + " personaggi unici");
                    Snackbar.make(findViewById(android.R.id.content),
                        "Rimossi " + removed + " duplicati", Snackbar.LENGTH_LONG).show();
                });
            } catch (Exception e) {
                mainHandler.post(() -> {
                    btnCleanDuplicates.setEnabled(true);
                    btnCleanDuplicates.setText("Rimuovi Duplicati");
                });
            }
        });
    }

    // ── HTTP Helpers ────────────────────────────────────────────────────────

    private String httpGet(String urlStr) {
        try {
            AuthManager auth = ((ChatApplication) getApplication()).getAuthManager();
            AuthManager.HttpResponse httpResp = auth.requestWithRefresh(urlStr, "GET", null, 30000);
            if (httpResp.statusCode == 200) return httpResp.body;
        } catch (Exception e) {
            return null;
        }
        return null;
    }

    private String httpPost(String urlStr, String body) {
        try {
            AuthManager auth = ((ChatApplication) getApplication()).getAuthManager();
            AuthManager.HttpResponse httpResp = auth.requestWithRefresh(urlStr, "POST", body, 60000);
            if (httpResp.statusCode >= 200 && httpResp.statusCode < 300) return httpResp.body;
        } catch (Exception e) {
            return null;
        }
        return null;
    }
}
