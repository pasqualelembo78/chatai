package com.intelligame.chatai;

import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.CheckBox;
import android.widget.Spinner;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.Fragment;

import com.google.android.material.button.MaterialButton;
import com.google.android.material.textfield.TextInputEditText;
import com.google.android.material.snackbar.Snackbar;

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

public class CreateFragment extends Fragment {

    private TextInputEditText fieldName, fieldAge, fieldRole, fieldAvatar;
    private TextInputEditText fieldDescription, fieldTags, fieldEssence, fieldPersonality;
    private TextInputEditText fieldSpeakingStyle, fieldBackstory, fieldHobbies, fieldSystemPrompt;
    private Spinner fieldCategory;
    private CheckBox fieldIsAdult;
    private MaterialButton btnCreate;
    private TextView statusText;

    private ExecutorService executor = new SafeExecutor();
    private Handler mainHandler = new Handler(Looper.getMainLooper());
    private AuthManager mAuth;

    private List<String> categoryIds = new ArrayList<>();
    private List<String> categoryNames = new ArrayList<>();
    private String baseUrl;

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater, @Nullable ViewGroup container, @Nullable Bundle savedInstanceState) {
        View view = inflater.inflate(R.layout.fragment_create, container, false);

        ChatApplication app = (ChatApplication) requireActivity().getApplication();
        PrefsManager prefs = app.getPrefs();
        mAuth = app.getAuthManager();
        baseUrl = prefs.getServerUrl().replace("/chat", "");

        fieldName = view.findViewById(R.id.field_name);
        fieldAge = view.findViewById(R.id.field_age);
        fieldRole = view.findViewById(R.id.field_role);
        fieldCategory = view.findViewById(R.id.field_category);
        fieldAvatar = view.findViewById(R.id.field_avatar);
        fieldDescription = view.findViewById(R.id.field_description);
        fieldTags = view.findViewById(R.id.field_tags);
        fieldEssence = view.findViewById(R.id.field_essence);
        fieldPersonality = view.findViewById(R.id.field_personality);
        fieldSpeakingStyle = view.findViewById(R.id.field_speaking_style);
        fieldBackstory = view.findViewById(R.id.field_backstory);
        fieldHobbies = view.findViewById(R.id.field_hobbies);
        fieldSystemPrompt = view.findViewById(R.id.field_system_prompt);
        fieldIsAdult = view.findViewById(R.id.field_is_adult);
        btnCreate = view.findViewById(R.id.btn_create);
        statusText = view.findViewById(R.id.status_text);

        loadCategories();

        btnCreate.setOnClickListener(v -> submitCharacter());

        return view;
    }

    @Override
    public void onStop() {
        super.onStop();
        if (executor != null) executor.shutdownNow();
    }

    private void loadCategories() {
        executor.execute(() -> {
            try {
                String json = httpGet(baseUrl + "/categories");
                if (json == null) return;
                JSONArray arr = new JSONArray(json);
                List<String> names = new ArrayList<>();
                List<String> ids = new ArrayList<>();
                for (int i = 0; i < arr.length(); i++) {
                    JSONObject obj = arr.getJSONObject(i);
                    ids.add(obj.getString("id"));
                    names.add(obj.optString("icon", "") + " " + obj.getString("name"));
                }
                categoryIds.clear();
                categoryIds.addAll(ids);
                categoryNames.clear();
                categoryNames.addAll(names);
                mainHandler.post(() -> {
                    ArrayAdapter<String> adapter = new ArrayAdapter<>(
                        requireContext(), android.R.layout.simple_spinner_item, categoryNames);
                    adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
                    fieldCategory.setAdapter(adapter);
                });
            } catch (Exception e) {
                mainHandler.post(() -> showStatus("Errore caricamento categorie", true));
            }
        });
    }

    private void submitCharacter() {
        String name = fieldName.getText().toString().trim();
        if (name.isEmpty()) {
            showStatus("Il nome è obbligatorio", true);
            return;
        }

        String ageStr = fieldAge.getText().toString().trim();
        int age;
        try {
            age = ageStr.isEmpty() ? 0 : Integer.parseInt(ageStr);
        } catch (NumberFormatException e) {
            showStatus("Inserisci un'età valida", true);
            return;
        }
        if (age < 18) {
            showStatus("L'età deve essere almeno 18 anni", true);
            return;
        }

        btnCreate.setEnabled(false);
        showStatus("Creazione in corso...", false);

        executor.execute(() -> {
            try {

                int catIndex = fieldCategory.getSelectedItemPosition();
                String category = catIndex >= 0 && catIndex < categoryIds.size()
                    ? categoryIds.get(catIndex) : "amicizia";

                String tagsStr = fieldTags.getText().toString().trim();
                JSONArray tagsArr = new JSONArray();
                if (!tagsStr.isEmpty()) {
                    String[] parts = tagsStr.split(",");
                    for (String p : parts) {
                        tagsArr.put(p.trim());
                    }
                }

                String hobbiesStr = fieldHobbies.getText().toString().trim();
                JSONArray hobbiesArr = new JSONArray();
                if (!hobbiesStr.isEmpty()) {
                    String[] parts = hobbiesStr.split(",");
                    for (String p : parts) {
                        hobbiesArr.put(p.trim());
                    }
                }

                ChatApplication app = (ChatApplication) requireActivity().getApplication();
                PrefsManager prefs = app.getPrefs();
                String userId = prefs.getUsername();

                String charId = name.toLowerCase().replaceAll("[^a-z0-9]", "_") + "_" + System.currentTimeMillis();

                JSONObject body = new JSONObject();
                body.put("id", charId);
                body.put("user_id", userId);
                body.put("name", name);
                body.put("age", age);
                body.put("role", fieldRole.getText().toString().trim());
                body.put("category", category);
                body.put("avatar", fieldAvatar.getText().toString().trim().isEmpty()
                    ? "💬" : fieldAvatar.getText().toString().trim());
                body.put("description", fieldDescription.getText().toString().trim());
                body.put("tags", tagsArr);
                body.put("is_adult", fieldIsAdult.isChecked());
                body.put("essence", fieldEssence.getText().toString().trim());
                body.put("personality", fieldPersonality.getText().toString().trim());
                body.put("speaking_style", fieldSpeakingStyle.getText().toString().trim());
                body.put("backstory", fieldBackstory.getText().toString().trim());
                body.put("hobbies", hobbiesArr);
                body.put("system_prompt", fieldSystemPrompt.getText().toString().trim());

                app.getLocalDb().saveCharacter(body);

                String response = httpPost(baseUrl + "/characters", body.toString());
                if (response != null) {
                    mainHandler.post(() -> {
                        showStatus("Personaggio creato!", false);
                        btnCreate.setEnabled(true);
                        clearFields();
                        Snackbar.make(requireView(), "Personaggio \"" + name + "\" creato!", Snackbar.LENGTH_LONG).show();
                    });
                } else {
                    mainHandler.post(() -> {
                        showStatus("Errore durante la creazione", true);
                        btnCreate.setEnabled(true);
                    });
                }
            } catch (Exception e) {
                mainHandler.post(() -> {
                    showStatus("Errore: " + e.getMessage(), true);
                    btnCreate.setEnabled(true);
                });
            }
        });
    }

    private void clearFields() {
        fieldName.setText("");
        fieldAge.setText("");
        fieldRole.setText("");
        fieldAvatar.setText("");
        fieldDescription.setText("");
        fieldTags.setText("");
        fieldEssence.setText("");
        fieldPersonality.setText("");
        fieldSpeakingStyle.setText("");
        fieldBackstory.setText("");
        fieldHobbies.setText("");
        fieldSystemPrompt.setText("");
        fieldIsAdult.setChecked(false);
        fieldCategory.setSelection(0);
    }

    private void showStatus(String msg, boolean isError) {
        statusText.setText(msg);
        statusText.setTextColor(isError
            ? getResources().getColor(R.color.error)
            : getResources().getColor(R.color.on_surface_variant));
        statusText.setVisibility(View.VISIBLE);
    }

    private String httpGet(String urlStr) {
        try {
            AuthManager.HttpResponse httpResp = mAuth.requestWithRefresh(urlStr, "GET", null, 5000);
            if (httpResp.statusCode == 200) return httpResp.body;
        } catch (Exception e) {
            return null;
        }
        return null;
    }

    private String httpPost(String urlStr, String body) {
        try {
            AuthManager.HttpResponse httpResp = mAuth.requestWithRefresh(urlStr, "POST", body, 10000);
            if (httpResp.statusCode >= 200 && httpResp.statusCode < 300) return httpResp.body;
        } catch (Exception e) {
            return null;
        }
        return null;
    }
}
