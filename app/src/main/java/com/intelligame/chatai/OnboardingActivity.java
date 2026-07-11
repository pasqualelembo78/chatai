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

import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.ArrayList;
import java.util.List;

public class OnboardingActivity extends Activity {

    private String selectedGender;
    private String selectedAge;
    private final List<String> selectedInterests = new ArrayList<>();

    private Button genderM, genderF, genderNB;
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

        age18_24 = findViewById(R.id.age_18_24);
        age25_34 = findViewById(R.id.age_25_34);
        age35_44 = findViewById(R.id.age_35_44);
        age45_plus = findViewById(R.id.age_45_plus);

        confirmButton = findViewById(R.id.btn_onboarding_confirm);
        interestCounter = findViewById(R.id.interest_counter);

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
        confirmButton.setEnabled(selectedGender != null);
    }

    private void submitOnboarding() {
        confirmButton.setEnabled(false);
        confirmButton.setText("Salvataggio...");

        new Thread(() -> {
            try {
                String token = mAuth.getAccessToken();
                String baseUrl = ((ChatApplication) getApplication()).getCurrentUrl();
                String apiUrl = baseUrl.replace("/chat", "") + "/user/preferences";

                URL url = new URL(apiUrl);
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("PUT");
                conn.setConnectTimeout(15000);
                conn.setReadTimeout(15000);
                conn.setRequestProperty("Content-Type", "application/json");
                conn.setRequestProperty("Authorization", "Bearer " + token);
                conn.setDoOutput(true);

                JSONObject body = new JSONObject();
                body.put("gender_interest", selectedGender);
                if (selectedAge != null) {
                    body.put("age_range", selectedAge);
                }
                JSONArray interestsArr = new JSONArray();
                for (String s : selectedInterests) {
                    interestsArr.put(s);
                }
                body.put("interests", interestsArr);

                OutputStream os = conn.getOutputStream();
                os.write(body.toString().getBytes());
                os.close();

                int code = conn.getResponseCode();
                conn.disconnect();

                runOnUiThread(() -> {
                    if (code == 200 || code == 201 || code == 204) {
                        Intent intent = new Intent(OnboardingActivity.this, MainActivity.class);
                        intent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_NEW_TASK);
                        startActivity(intent);
                        finish();
                    } else {
                        confirmButton.setEnabled(true);
                        confirmButton.setText("Entra in ChatAI");
                        Toast.makeText(this, "Errore salvataggio preferenze (" + code + ")", Toast.LENGTH_LONG).show();
                    }
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    confirmButton.setEnabled(true);
                    confirmButton.setText("Entra in ChatAI");
                    Toast.makeText(this, "Errore di rete: " + e.getMessage(), Toast.LENGTH_LONG).show();
                });
            }
        }).start();
    }
}
