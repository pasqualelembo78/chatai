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
    private android.widget.EditText userAgeInput;
    private Button age18_24, age25_34, age35_44, age45_plus;
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
        userAgeInput = findViewById(R.id.user_age_input);

        age18_24 = findViewById(R.id.age_18_24);
        age25_34 = findViewById(R.id.age_25_34);
        age35_44 = findViewById(R.id.age_35_44);
        age45_plus = findViewById(R.id.age_45_plus);

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

        // Age listeners (single select)
        View.OnClickListener ageListener = v -> {
            resetAgeSelection();
            selectChip((Button) v);
            if (v == age18_24) selectedAge = "18-24";
            else if (v == age25_34) selectedAge = "25-34";
            else if (v == age35_44) selectedAge = "35-44";
            else if (v == age45_plus) selectedAge = "45+";
        };
        age18_24.setOnClickListener(ageListener);
        age25_34.setOnClickListener(ageListener);
        age35_44.setOnClickListener(ageListener);
        age45_plus.setOnClickListener(ageListener);

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

    private void resetAgeSelection() {
        deselectChip(age18_24);
        deselectChip(age25_34);
        deselectChip(age35_44);
        deselectChip(age45_plus);
        selectedAge = null;
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
                    String savedAgeRange = prefs.optString("age_range", "");
                    String savedUserGender = prefs.optString("user_gender", "");
                    int savedUserAge = prefs.optInt("user_age", 0);

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

                        // Restore user_age
                        if (savedUserAge > 0) {
                            userAgeInput.setText(String.valueOf(savedUserAge));
                        }

                        // Restore age_range selection
                        if ("18-24".equals(savedAgeRange)) {
                            selectChip(age18_24); selectedAge = "18-24";
                        } else if ("25-34".equals(savedAgeRange)) {
                            selectChip(age25_34); selectedAge = "25-34";
                        } else if ("35-44".equals(savedAgeRange)) {
                            selectChip(age35_44); selectedAge = "35-44";
                        } else if ("45+".equals(savedAgeRange)) {
                            selectChip(age45_plus); selectedAge = "45+";
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
                conn.disconnect();
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
                if (selectedAge != null) {
                    body.put("age_range", selectedAge);
                }
                if (userGender != null) {
                    body.put("user_gender", userGender);
                }
                String ageText = userAgeInput.getText().toString().trim();
                if (!ageText.isEmpty()) {
                    try {
                        int age = Integer.parseInt(ageText);
                        if (age >= 18 && age <= 100) {
                            body.put("user_age", age);
                        }
                    } catch (NumberFormatException ignored) {}
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
