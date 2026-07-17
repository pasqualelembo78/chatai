package com.intelligame.chatai;

import android.app.Activity;
import android.content.Intent;
import android.content.res.ColorStateList;
import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;

import androidx.core.content.ContextCompat;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.ArrayList;
import java.util.List;

public class OnboardingActivity extends Activity {

    private String selectedGender;
    private String selectedAge;
    private String userGender;
    private int userAge = 0;
    private final List<String> selectedInterests = new ArrayList<>();

    private Button genderM, genderF, genderNB;
    private Button userGenderF, userGenderM, userGenderNB;
    private Button confirmButton;
    private TextView interestCounter;

    private final List<Button> tagButtons = new ArrayList<>();

    private AuthManager mAuth;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_onboarding);

        ChatApplication app = (ChatApplication) getApplication();
        mAuth = app.getAuthManager();

        genderM = findViewById(R.id.gender_chip_m);
        genderF = findViewById(R.id.gender_chip_f);
        genderNB = findViewById(R.id.gender_chip_nb);

        userGenderF = findViewById(R.id.user_gender_f);
        userGenderM = findViewById(R.id.user_gender_m);
        userGenderNB = findViewById(R.id.user_gender_nb);

        confirmButton = findViewById(R.id.btn_onboarding_confirm);
        interestCounter = findViewById(R.id.interest_counter);

        // If editing, change button text and load existing preferences
        boolean isEditing = getIntent().getBooleanExtra("editing", false);
        if (isEditing) {
            confirmButton.setText("Salva modifiche");
            loadExistingPreferences();
        }

        tagButtons.add(findViewById(R.id.tag_anime));
        tagButtons.add(findViewById(R.id.tag_mafia));
        tagButtons.add(findViewById(R.id.tag_romantico));
        tagButtons.add(findViewById(R.id.tag_oc));
        tagButtons.add(findViewById(R.id.tag_piccante));
        tagButtons.add(findViewById(R.id.tag_premuroso));
        tagButtons.add(findViewById(R.id.tag_protettivo));
        tagButtons.add(findViewById(R.id.tag_cattivo));
        tagButtons.add(findViewById(R.id.tag_realizzato_dai_fan));
        tagButtons.add(findViewById(R.id.tag_fittizio));
        tagButtons.add(findViewById(R.id.tag_amore_proibito));
        tagButtons.add(findViewById(R.id.tag_punto_di_vista_femminile));
        tagButtons.add(findViewById(R.id.tag_atletico));
        tagButtons.add(findViewById(R.id.tag_musica));
        tagButtons.add(findViewById(R.id.tag_arte));
        tagButtons.add(findViewById(R.id.tag_gaming));
        tagButtons.add(findViewById(R.id.tag_sport));
        tagButtons.add(findViewById(R.id.tag_cucina));
        tagButtons.add(findViewById(R.id.tag_viaggi));
        tagButtons.add(findViewById(R.id.tag_tecnologia));
        tagButtons.add(findViewById(R.id.tag_moda));
        tagButtons.add(findViewById(R.id.tag_natura));
        tagButtons.add(findViewById(R.id.tag_storia));
        tagButtons.add(findViewById(R.id.tag_scienza));
        tagButtons.add(findViewById(R.id.tag_mistero));
        tagButtons.add(findViewById(R.id.tag_spiritualita));

        // Gender listeners (single select)
        View.OnClickListener genderListener = v -> {
            resetGenderSelection();
            selectChip((Button) v);
            if (v == genderM) selectedGender = "maschile";
            else if (v == genderF) selectedGender = "femminile";
            else if (v == genderNB) selectedGender = "non binario";
            updateConfirmButton();
        };
        genderM.setOnClickListener(genderListener);
        genderF.setOnClickListener(genderListener);
        genderNB.setOnClickListener(genderListener);

        // User gender listeners (single select)
        View.OnClickListener userGenderListener = v -> {
            resetUserGenderSelection();
            selectChip((Button) v);
            if (v == userGenderF) userGender = "female";
            else if (v == userGenderM) userGender = "male";
            else if (v == userGenderNB) userGender = "non-binary";
            updateConfirmButton();
        };
        userGenderF.setOnClickListener(userGenderListener);
        userGenderM.setOnClickListener(userGenderListener);
        userGenderNB.setOnClickListener(userGenderListener);

        // Tag listeners (multi select, max 3)
        for (Button btn : tagButtons) {
            btn.setOnClickListener(v -> {
                Button b = (Button) v;
                String tag = b.getText().toString();
                if (b.getBackgroundTintList() != null
                        && b.getBackgroundTintList().getDefaultColor()
                        == ContextCompat.getColor(this, R.color.category_chip_selected)) {
                    // Deselect
                    deselectChip(b);
                    selectedInterests.remove(tag);
                } else {
                    if (selectedInterests.size() >= 3) {
                        Toast.makeText(this, "Max 3 categorie", Toast.LENGTH_SHORT).show();
                        return;
                    }
                    selectChip(b);
                    selectedInterests.add(tag);
                }
                updateInterestCounter();
            });
        }

        confirmButton.setOnClickListener(v -> submitOnboarding());
    }

    private void resetGenderSelection() {
        deselectChip(genderM);
        deselectChip(genderF);
        deselectChip(genderNB);
        selectedGender = null;
    }

    private void resetUserGenderSelection() {
        deselectChip(userGenderF);
        deselectChip(userGenderM);
        deselectChip(userGenderNB);
        userGender = null;
    }

    private void selectChip(Button btn) {
        btn.setBackgroundTintList(
                ColorStateList.valueOf(
                        ContextCompat.getColor(this, R.color.category_chip_selected)));
        btn.setTextColor(ContextCompat.getColor(this, R.color.on_primary));
    }

    private void deselectChip(Button btn) {
        btn.setBackgroundTintList(
                ColorStateList.valueOf(
                        ContextCompat.getColor(this, R.color.category_chip_bg)));
        btn.setTextColor(ContextCompat.getColor(this, R.color.on_surface));
    }

    private void updateInterestCounter() {
        interestCounter.setText(selectedInterests.size() + "/3 selezionati");
    }

    private void updateConfirmButton() {
        confirmButton.setEnabled(selectedGender != null && userGender != null);
    }

    private void loadExistingPreferences() {
        new Thread(() -> {
            try {
                String baseUrl = ((ChatApplication) getApplication()).getCurrentUrl();
                String apiUrl = baseUrl.replace("/chat", "") + "/user/preferences";
                AuthManager.HttpResponse httpResp = mAuth.requestWithRefresh(apiUrl, "GET", null, 10000);

                if (httpResp.statusCode == 200) {
                    JSONObject prefs = new JSONObject(httpResp.body);

                    String savedGenderInterest = prefs.optString("gender_interest", "");
                    String savedUserGender = prefs.optString("user_gender", "");

                    runOnUiThread(() -> {
                        // Restore gender_interest selection
                        if ("maschile".equals(savedGenderInterest)) {
                            selectChip(genderM); selectedGender = "maschile";
                        } else if ("femminile".equals(savedGenderInterest)) {
                            selectChip(genderF); selectedGender = "femminile";
                        } else if ("non binario".equals(savedGenderInterest)) {
                            selectChip(genderNB); selectedGender = "non binario";
                        }

                        // Restore user_gender selection
                        if ("female".equals(savedUserGender)) {
                            selectChip(userGenderF); userGender = "female";
                        } else if ("male".equals(savedUserGender)) {
                            selectChip(userGenderM); userGender = "male";
                        } else if ("non-binary".equals(savedUserGender)) {
                            selectChip(userGenderNB); userGender = "non-binary";
                        }

                        // Restore interest tags
                        JSONArray tags = prefs.optJSONArray("interest_tags");
                        if (tags != null) {
                            for (int i = 0; i < tags.length(); i++) {
                                String tag = tags.optString(i);
                                for (Button btn : tagButtons) {
                                    if (btn.getText().toString().equals(tag)) {
                                        selectChip(btn);
                                        selectedInterests.add(tag);
                                        break;
                                    }
                                }
                            }
                            updateInterestCounter();
                        }
                    });
                }
            } catch (Exception e) {
                e.printStackTrace();
            }
        }).start();
    }

    private void submitOnboarding() {
        confirmButton.setEnabled(false);
        confirmButton.setText("Salvataggio...");

        new Thread(() -> {
            try {
                String baseUrl = ((ChatApplication) getApplication()).getCurrentUrl();
                String apiUrl = baseUrl.replace("/chat", "") + "/user/preferences";

                JSONObject body = new JSONObject();
                body.put("gender_interest", selectedGender);
                if (userGender != null) {
                    body.put("user_gender", userGender);
                }
                JSONArray interestsArr = new JSONArray();
                for (String s : selectedInterests) {
                    interestsArr.put(s);
                }
                body.put("interests", interestsArr);

                AuthManager.HttpResponse httpResp = mAuth.requestWithRefresh(apiUrl, "PUT", body.toString(), 15000);

                runOnUiThread(() -> {
                    if (httpResp.statusCode == 200 || httpResp.statusCode == 201 || httpResp.statusCode == 204) {
                        Intent intent = new Intent(OnboardingActivity.this, MainActivity.class);
                        intent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_NEW_TASK);
                        startActivity(intent);
                        finish();
                    } else {
                        confirmButton.setEnabled(true);
                        confirmButton.setText("Entra in Aria");
                        Toast.makeText(this, "Errore salvataggio preferenze (" + httpResp.statusCode + ")", Toast.LENGTH_LONG).show();
                    }
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    confirmButton.setEnabled(true);
                    confirmButton.setText("Entra in Aria");
                    Toast.makeText(this, "Errore di rete: " + e.getMessage(), Toast.LENGTH_LONG).show();
                });
            }
        }).start();
    }
}
