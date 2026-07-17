package com.intelligame.chatai;

import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ImageButton;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.cardview.widget.CardView;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.view.WindowCompat;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.google.android.material.button.MaterialButton;
import com.google.android.material.imageview.ShapeableImageView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class CharacterDetailActivity extends AppCompatActivity {

    private ShapeableImageView avatarImage;
    private TextView avatarEmoji, name, author, description, descriptionFull, tags;
    private TextView ageRole, categoryBadge;
    private TextView statsInteractions, statsLikes;
    private TextView backstory, hobbies, personality, scenario;
    private CardView backstoryCard, scenarioCard, evolutionCard;
    private TextView evoStageIcon, evoStageName, evoProgressText;
    private TextView evoUnlockedLabel, evoUnlockedList, evoNextLabel, evoNextName;
    private android.widget.ProgressBar evoProgress;
    private MaterialButton startChatBtn;
    private ImageButton favoriteBtn, expandInfoBtn, backBtn, shareBtn, menuBtn;

    // Tabs
    private View tabDetails, tabQuestions, tabScenes;
    private View indicatorDetails, indicatorQuestions, indicatorScenes;
    private View contentDetails, contentQuestions, contentScenes;
    private TextView descriptionExpand;

    // Questions
    private RecyclerView questionsList;
    private QuestionsAdapter questionsAdapter;
    private List<String> introductoryQuestions = new ArrayList<>();

    private ChatApplication app;
    private LocalDatabaseHelper mLocalDb;
    private AuthManager mAuth;
    private String characterId;
    private String baseUrl;
    private String characterName;
    private String currentAvatarImage;
    private String currentEmoji;
    private boolean isFavorite = false;

    private final ExecutorService executor = new SafeExecutor();
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        WindowCompat.setDecorFitsSystemWindows(getWindow(), false);

        setContentView(R.layout.fragment_character_detail);

        View root = findViewById(android.R.id.content);
        ViewCompat.setOnApplyWindowInsetsListener(root, (v, insets) -> {
            int bottom = insets.getInsets(
                WindowInsetsCompat.Type.systemBars() | WindowInsetsCompat.Type.ime()
            ).bottom;
            v.setPadding(0, 0, 0, bottom);
            return WindowInsetsCompat.CONSUMED;
        });

        app = (ChatApplication) getApplication();
        mLocalDb = app.getLocalDb();
        mAuth = app.getAuthManager();
        baseUrl = app.getPrefs().getServerUrl();

        characterId = getIntent().getStringExtra("character_id");
        if (characterId == null) {
            finish();
            return;
        }

        initViews();
        setupTabs();
        setupListeners();

        loadCharacterDetail();
    }

    private void initViews() {
        // Header
        avatarImage = findViewById(R.id.detail_avatar_image);
        avatarEmoji = findViewById(R.id.detail_avatar_emoji);
        name = findViewById(R.id.detail_name);
        author = findViewById(R.id.detail_author);
        description = findViewById(R.id.detail_description);
        descriptionExpand = findViewById(R.id.detail_description_expand);
        descriptionFull = findViewById(R.id.detail_description_full);
        ageRole = findViewById(R.id.detail_age_role);
        categoryBadge = findViewById(R.id.detail_category_badge);
        statsInteractions = findViewById(R.id.detail_stats_interactions);
        statsLikes = findViewById(R.id.detail_stats_likes);
        tags = findViewById(R.id.detail_tags);
        startChatBtn = findViewById(R.id.btn_start_chat);
        favoriteBtn = findViewById(R.id.btn_favorite);
        expandInfoBtn = findViewById(R.id.btn_expand_info);
        backBtn = findViewById(R.id.btn_back);
        shareBtn = findViewById(R.id.btn_share);
        menuBtn = findViewById(R.id.btn_menu);

        // Tabs
        tabDetails = findViewById(R.id.tab_details);
        tabQuestions = findViewById(R.id.tab_questions);
        tabScenes = findViewById(R.id.tab_scenes);
        indicatorDetails = findViewById(R.id.tab_indicator_details);
        indicatorQuestions = findViewById(R.id.tab_indicator_questions);
        indicatorScenes = findViewById(R.id.tab_indicator_scenes);
        contentDetails = findViewById(R.id.content_details);
        contentQuestions = findViewById(R.id.content_questions);
        contentScenes = findViewById(R.id.content_scenes);

        // Details tab
        backstory = findViewById(R.id.detail_backstory);
        backstoryCard = findViewById(R.id.detail_backstory_card);
        scenario = findViewById(R.id.detail_scenario);
        scenarioCard = findViewById(R.id.detail_scenario_card);
        hobbies = findViewById(R.id.detail_hobbies);
        personality = findViewById(R.id.detail_personality);

        // Evolution
        evolutionCard = findViewById(R.id.detail_evolution_card);
        evoStageIcon = findViewById(R.id.detail_evo_stage_icon);
        evoStageName = findViewById(R.id.detail_evo_stage_name);
        evoProgressText = findViewById(R.id.detail_evo_progress_text);
        evoProgress = findViewById(R.id.detail_evo_progress);
        evoUnlockedLabel = findViewById(R.id.detail_evo_unlocked_label);
        evoUnlockedList = findViewById(R.id.detail_evo_unlocked_list);
        evoNextLabel = findViewById(R.id.detail_evo_next_label);
        evoNextName = findViewById(R.id.detail_evo_next_name);

        // Questions
        questionsList = findViewById(R.id.questions_list);
        questionsList.setLayoutManager(new LinearLayoutManager(this));
        questionsAdapter = new QuestionsAdapter(introductoryQuestions, question -> {
            // Start chat with this question
            startChatWithMessage(question);
        });
        questionsList.setAdapter(questionsAdapter);
    }

    private void setupTabs() {
        selectTab(0); // Default to details tab
    }

    private void selectTab(int tabIndex) {
        // Hide all indicators
        indicatorDetails.setVisibility(View.GONE);
        indicatorQuestions.setVisibility(View.GONE);
        indicatorScenes.setVisibility(View.GONE);

        // Hide all content
        contentDetails.setVisibility(View.GONE);
        contentQuestions.setVisibility(View.GONE);
        contentScenes.setVisibility(View.GONE);

        // Reset all tab icon tints
        resetTabTint(tabDetails);
        resetTabTint(tabQuestions);
        resetTabTint(tabScenes);

        // Show selected and highlight
        switch (tabIndex) {
            case 0:
                indicatorDetails.setVisibility(View.VISIBLE);
                contentDetails.setVisibility(View.VISIBLE);
                highlightTab(tabDetails);
                break;
            case 1:
                indicatorQuestions.setVisibility(View.VISIBLE);
                contentQuestions.setVisibility(View.VISIBLE);
                highlightTab(tabQuestions);
                break;
            case 2:
                indicatorScenes.setVisibility(View.VISIBLE);
                contentScenes.setVisibility(View.VISIBLE);
                highlightTab(tabScenes);
                break;
        }
    }

    private void resetTabTint(View tab) {
        if (tab instanceof LinearLayout) {
            LinearLayout layout = (LinearLayout) tab;
            for (int i = 0; i < layout.getChildCount(); i++) {
                View child = layout.getChildAt(i);
                if (child instanceof ImageView) {
                    child.setAlpha(0.5f);
                } else if (child instanceof TextView) {
                    ((TextView) child).setTextColor(getColor(R.color.on_surface_dim));
                }
            }
        }
    }

    private void highlightTab(View tab) {
        if (tab instanceof LinearLayout) {
            LinearLayout layout = (LinearLayout) tab;
            for (int i = 0; i < layout.getChildCount(); i++) {
                View child = layout.getChildAt(i);
                if (child instanceof ImageView) {
                    child.setAlpha(1.0f);
                } else if (child instanceof TextView) {
                    ((TextView) child).setTextColor(getColor(R.color.primary));
                }
            }
        }
    }

    private void setupListeners() {
        // Back button
        backBtn.setOnClickListener(v -> finish());

        // Share button (placeholder)
        shareBtn.setOnClickListener(v -> {
            // TODO: Implement share functionality
        });

        // Menu button (placeholder)
        menuBtn.setOnClickListener(v -> {
            // TODO: Implement menu
        });

        // Favorite button
        favoriteBtn.setOnClickListener(v -> {
            isFavorite = !isFavorite;
            favoriteBtn.setImageResource(isFavorite ?
                R.drawable.ic_favorite_filled : R.drawable.ic_favorite_border);
            favoriteBtn.setColorFilter(isFavorite ?
                0xFFFF0000 : getColor(R.color.on_surface_dim));
        });

        // Expand info button
        expandInfoBtn.setOnClickListener(v -> {
            // Scroll to details tab
            selectTab(0);
        });

        // Start chat button
        startChatBtn.setOnClickListener(v -> {
            startChatWithMessage(null);
        });

        // Tab click listeners
        tabDetails.setOnClickListener(v -> selectTab(0));
        tabQuestions.setOnClickListener(v -> selectTab(1));
        tabScenes.setOnClickListener(v -> selectTab(2));

        // Description expand
        descriptionExpand.setOnClickListener(v -> {
            if (description.getMaxLines() == 2) {
                description.setMaxLines(Integer.MAX_VALUE);
                descriptionExpand.setText("meno");
            } else {
                description.setMaxLines(2);
                descriptionExpand.setText("...Altro");
            }
        });

        // Backstory expand
        backstoryCard.setOnClickListener(v -> {
            if (backstory.getMaxLines() == 3) {
                backstory.setMaxLines(Integer.MAX_VALUE);
            } else {
                backstory.setMaxLines(3);
            }
        });

        // Scenario expand
        scenarioCard.setOnClickListener(v -> {
            if (scenario.getMaxLines() == 3) {
                scenario.setMaxLines(Integer.MAX_VALUE);
            } else {
                scenario.setMaxLines(3);
            }
        });
    }

    private void startChatWithMessage(String message) {
        ChatApplication ca = (ChatApplication) getApplication();
        PrefsManager prefs = ca.getPrefs();
        prefs.setCharacterId(characterId);
        if (!prefs.hasUsername()) {
            prefs.setUsername("user_" + System.currentTimeMillis());
        }

        Intent intent = new Intent(this, MainActivity.class);
        intent.putExtra("character_id", characterId);
        intent.putExtra("character_name", characterName != null ? characterName : characterId);
        if (message != null) {
            intent.putExtra("initial_message", message);
        }
        if (currentAvatarImage != null) {
            intent.putExtra("character_avatar_image", currentAvatarImage);
        }
        if (currentEmoji != null) {
            intent.putExtra("character_emoji", currentEmoji);
        }
        intent.setFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        startActivity(intent);
    }

    private void loadCharacterDetail() {
        try {
            executor.execute(() -> {
                try {
                    String json = httpGet(baseUrl + "/characters/" + characterId);
                    if (json == null) {
                        mainHandler.post(this::loadOfflineDetail);
                        return;
                    }
                    JSONObject obj = new JSONObject(json);
                    mainHandler.post(() -> bindData(obj));
                } catch (Exception e) {
                    mainHandler.post(this::loadOfflineDetail);
                }
            });
        } catch (java.util.concurrent.RejectedExecutionException e) {
            // Executor shutting down
        }

        String userId = app.getPrefs().getUsername();
        if (userId != null) {
            final String uid = userId;
            try {
                executor.execute(() -> {
                    try {
                        String url = baseUrl + "/evolution?user_id=" + uid + "&character_id=" + characterId;
                        String json = httpGet(url);
                        if (json != null) {
                            JSONObject obj = new JSONObject(json);
                            JSONObject evo = obj.optJSONObject("evolution");
                            JSONArray stages = obj.optJSONArray("stages");
                            if (evo != null) {
                                try { evo.put("user_id", uid); evo.put("character_id", characterId); } catch (Exception ignored) {}
                                mLocalDb.saveEvolution(evo);
                            }
                            JSONObject finalEvo = evo;
                            mainHandler.post(() -> bindEvolution(finalEvo, stages));
                            return;
                        }
                    } catch (Exception ignored) {}
                    // Fallback offline
                    try {
                        executor.execute(() -> {
                            JSONObject cached = mLocalDb.getEvolution(uid, characterId);
                            if (cached != null) {
                                mainHandler.post(() -> bindEvolution(cached, null));
                            }
                        });
                    } catch (java.util.concurrent.RejectedExecutionException e) {
                        // Executor shutting down
                    }
                });
            } catch (java.util.concurrent.RejectedExecutionException e) {
                // Executor shutting down
            }
        }
    }

    private void bindData(JSONObject obj) {
        String emoji = obj.optString("avatar", "\uD83D\uDC64");
        String charName = obj.optString("name", characterId);
        String catName = obj.optString("category_name", obj.optString("category", ""));
        int ageInt = obj.optInt("age", 0);
        String charAge = ageInt > 0 ? String.valueOf(ageInt) : "";
        String charRole = obj.optString("role", "");
        String desc = obj.optString("description", "");
        String backstoryStr = obj.optString("backstory", "");
        String personalityStr = obj.optString("personality", "");

        // Tags
        String tagsStr = "";
        JSONArray tagsArr = obj.optJSONArray("tags");
        if (tagsArr != null) {
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < tagsArr.length(); i++) {
                if (i > 0) sb.append(" · ");
                sb.append(tagsArr.optString(i, ""));
            }
            tagsStr = sb.toString();
        }

        // Hobbies
        String hobbiesStr = "";
        JSONArray hobbiesArr = obj.optJSONArray("hobbies");
        if (hobbiesArr != null) {
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < hobbiesArr.length(); i++) {
                if (i > 0) sb.append("\n");
                String hobby = hobbiesArr.optString(i, "");
                if (hobby.contains("{")) {
                    try {
                        JSONObject hobbyObj = new JSONObject(hobby);
                        sb.append("• ").append(hobbyObj.optString("name", ""))
                          .append(" (").append(hobbyObj.optString("skill", "")).append(")");
                    } catch (Exception e) {
                        sb.append("• ").append(hobby);
                    }
                } else {
                    sb.append("• ").append(hobby);
                }
            }
            hobbiesStr = sb.toString();
        }

        characterName = charName;

        // Avatar
        String avatarImageName = obj.optString("avatar_image", null);
        currentAvatarImage = avatarImageName;
        currentEmoji = emoji;
        AvatarLoader.loadAvatar(this, avatarImageName, avatarImage, avatarEmoji, emoji);

        // Name and author
        name.setText(charName);
        String authorName = obj.optString("author", "");
        if (!authorName.isEmpty()) {
            author.setText("di " + authorName);
            author.setVisibility(View.VISIBLE);
        } else {
            author.setVisibility(View.GONE);
        }

        // Stats
        int conversations = obj.optInt("conversations", 0);
        statsInteractions.setText(formatCount(conversations));
        statsLikes.setText("0"); // Placeholder

        // Description
        description.setText(desc);
        descriptionExpand.setVisibility(desc.length() > 100 ? View.VISIBLE : View.GONE);
        descriptionFull.setText(desc);

        // Category and age/role
        categoryBadge.setText(catName);
        categoryBadge.setVisibility(catName.isEmpty() ? View.GONE : View.VISIBLE);

        String ageRoleStr = "";
        if (!charAge.isEmpty()) ageRoleStr += charAge + " anni";
        if (!charRole.isEmpty()) {
            if (!ageRoleStr.isEmpty()) ageRoleStr += " · ";
            ageRoleStr += charRole;
        }
        ageRole.setText(ageRoleStr);
        ageRole.setVisibility(ageRoleStr.isEmpty() ? View.GONE : View.VISIBLE);

        // Tags
        tags.setText(tagsStr);
        tags.setVisibility(tagsStr.isEmpty() ? View.GONE : View.VISIBLE);

        // Backstory
        if (!backstoryStr.isEmpty()) {
            backstory.setText(backstoryStr);
            backstoryCard.setVisibility(View.VISIBLE);
        } else {
            backstoryCard.setVisibility(View.GONE);
        }

        // Scenario
        String scenarioStr = obj.optString("opening_scenario", "");
        if (!scenarioStr.isEmpty()) {
            scenario.setText(scenarioStr);
            scenarioCard.setVisibility(View.VISIBLE);
        } else {
            scenarioCard.setVisibility(View.GONE);
        }

        // Hobbies
        if (!hobbiesStr.isEmpty()) {
            ((TextView) findViewById(R.id.detail_hobbies_label)).setVisibility(View.VISIBLE);
            hobbies.setText(hobbiesStr);
            hobbies.setVisibility(View.VISIBLE);
        } else {
            ((TextView) findViewById(R.id.detail_hobbies_label)).setVisibility(View.GONE);
            hobbies.setVisibility(View.GONE);
        }

        // Personality
        if (!personalityStr.isEmpty()) {
            ((TextView) findViewById(R.id.detail_personality_label)).setVisibility(View.VISIBLE);
            personality.setText(personalityStr);
            personality.setVisibility(View.VISIBLE);
        } else {
            ((TextView) findViewById(R.id.detail_personality_label)).setVisibility(View.GONE);
            personality.setVisibility(View.GONE);
        }

        // Generate introductory questions
        generateIntroductoryQuestions(charName, charRole, desc);
    }

    private void generateIntroductoryQuestions(String name, String role, String description) {
        introductoryQuestions.clear();

        // Basic questions based on character
        introductoryQuestions.add("Ciao! Come stai oggi?");
        introductoryQuestions.add("Raccontami di te, cosa ti piace fare?");

        if (!role.isEmpty()) {
            introductoryQuestions.add("Come hai iniziato a fare " + role + "?");
            introductoryQuestions.add("Qual è la parte migliore del tuo lavoro?");
        }

        introductoryQuestions.add("Qual è il tuo sogno più grande?");
        introductoryQuestions.add("Se potessi avere un superpotere per un giorno, quale sceglieresti?");
        introductoryQuestions.add("Qual è la cosa più pazza che hai mai fatto?");
        introductoryQuestions.add("Cosa ti fa ridere di più?");

        questionsAdapter.notifyDataSetChanged();
    }

    private String formatCount(int count) {
        if (count >= 1000000) {
            return String.format("%.1fM", count / 1000000.0);
        } else if (count >= 1000) {
            return String.format("%.1fK", count / 1000.0);
        }
        return String.valueOf(count);
    }

    private String stageIcon(String stageId) {
        switch (stageId) {
            case "base": return "🌱";
            case "confidenza": return "🌿";
            case "amico": return "🤝";
            case "intima":
            case "ispirazione":
            case "grande_amico": return "🔥";
            case "profonda":
            case "musa":
            case "fratello": return "⭐";
            default: return "🌟";
        }
    }

    private void bindEvolution(JSONObject evo, JSONArray stages) {
        if (evo == null) return;
        try {
            String currentStage = evo.optString("current_stage", "base");
            int totalMessages = evo.optInt("total_messages", 0);

            JSONArray unlockedStages = evo.optJSONArray("unlocked_stages");
            JSONObject flags = evo.optJSONObject("flags");
            if (flags == null) flags = new JSONObject();

            String currentStageName = currentStage;
            int nextMinMessages = 0;
            String nextStageName = null;

            if (stages != null) {
                for (int i = 0; i < stages.length(); i++) {
                    JSONObject s = stages.getJSONObject(i);
                    String sid = s.optString("id", "");
                    if (sid.equals(currentStage)) {
                        currentStageName = s.optString("name", currentStage);
                        if (i + 1 < stages.length()) {
                            JSONObject next = stages.getJSONObject(i + 1);
                            nextStageName = next.optString("name");
                            nextMinMessages = next.optInt("min_messages", 0);
                        }
                    }
                }
            }

            evoStageIcon.setText(stageIcon(currentStage));
            evoStageName.setText(currentStageName);

            if (nextStageName != null) {
                int progress = Math.min(100, (totalMessages * 100) / Math.max(1, nextMinMessages));
                evoProgress.setProgress(progress);
                evoProgressText.setText(totalMessages + " / " + nextMinMessages + " messaggi");
                evoNextLabel.setVisibility(View.VISIBLE);
                evoNextName.setVisibility(View.VISIBLE);
                evoNextName.setText(nextStageName);
            } else {
                evoProgress.setProgress(Math.min(100, totalMessages));
                evoProgressText.setText(totalMessages + " messaggi" + (stages == null ? "" : " - Completato!"));
                evoNextLabel.setVisibility(View.GONE);
                evoNextName.setVisibility(View.GONE);
            }

            StringBuilder unlockedText = new StringBuilder();
            if (unlockedStages != null) {
                for (int i = 0; i < unlockedStages.length(); i++) {
                    String sid = unlockedStages.optString(i, "");
                    if (!sid.equals("base") && !sid.equals(currentStage)) {
                        if (unlockedText.length() > 0) unlockedText.append("\n");
                        unlockedText.append("✅ ").append(sid);
                    }
                }
            }
            java.util.Iterator<String> flagKeys = flags.keys();
            while (flagKeys.hasNext()) {
                String key = flagKeys.next();
                if (!key.startsWith("last_") && !key.equals(currentStage)) {
                    if (unlockedText.length() > 0) unlockedText.append("\n");
                    unlockedText.append("🔓 ").append(key);
                }
            }
            if (unlockedText.length() > 0) {
                evoUnlockedLabel.setVisibility(View.VISIBLE);
                evoUnlockedList.setVisibility(View.VISIBLE);
                evoUnlockedList.setText(unlockedText.toString());
            } else {
                evoUnlockedLabel.setVisibility(View.GONE);
                evoUnlockedList.setVisibility(View.GONE);
            }

            evolutionCard.setVisibility(View.VISIBLE);
        } catch (Exception ignored) {}
    }

    private void loadOfflineDetail() {
        try {
            String json = "{\"id\":\"" + characterId + "\",\"name\":\"" + characterId + "\",\"avatar\":\"\uD83D\uDC64\",\"description\":\"Caricamento dati non riuscito. Verifica la connessione al server.\"}";
            JSONObject obj = new JSONObject(json);
            bindData(obj);
        } catch (Exception ignored) {}
    }

    private String httpGet(String urlString) {
        try {
            AuthManager.HttpResponse httpResp = mAuth.requestWithRefresh(urlString, "GET", null, 8000);
            if (httpResp.statusCode == 200) return httpResp.body;
        } catch (Exception e) {
            return null;
        }
        return null;
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        executor.shutdown();
    }

    // Questions Adapter
    private static class QuestionsAdapter extends RecyclerView.Adapter<QuestionsAdapter.ViewHolder> {
        private final List<String> questions;
        private final OnQuestionClickListener listener;

        interface OnQuestionClickListener {
            void onQuestionClick(String question);
        }

        QuestionsAdapter(List<String> questions, OnQuestionClickListener listener) {
            this.questions = questions;
            this.listener = listener;
        }

        @NonNull
        @Override
        public ViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
            View view = LayoutInflater.from(parent.getContext())
                .inflate(R.layout.item_question, parent, false);
            return new ViewHolder(view);
        }

        @Override
        public void onBindViewHolder(@NonNull ViewHolder holder, int position) {
            String question = questions.get(position);
            holder.questionText.setText(question);
            holder.itemView.setOnClickListener(v -> listener.onQuestionClick(question));
        }

        @Override
        public int getItemCount() {
            return questions.size();
        }

        static class ViewHolder extends RecyclerView.ViewHolder {
            final TextView questionText;
            final ImageView arrowIcon;

            ViewHolder(View itemView) {
                super(itemView);
                questionText = itemView.findViewById(R.id.question_text);
                arrowIcon = itemView.findViewById(R.id.question_arrow);
            }
        }
    }
}
