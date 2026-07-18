package com.intelligame.chatai;

import android.content.Intent;
import android.os.Bundle;

import androidx.appcompat.app.AlertDialog;
import android.os.Handler;
import android.os.Looper;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.Fragment;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;
import androidx.viewpager2.widget.ViewPager2;
import com.google.android.material.snackbar.Snackbar;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class HomeFragment extends Fragment {

    private static class Cache {
        static List<Category> categories = null;
        static List<CharacterItem> characters = null;
        static String selectedCategoryId = null;
    }

    private ViewPager2 charactersPager;
    private EditText searchBar;
    private ProgressBar searchProgress;
    private LinearLayout emptyState;
    private TextView emptyStateTitle;
    private TextView emptyStateSubtitle;
    private TextView rewardIndicator;
    private RecyclerView searchFiltersRecycler;

    private CharacterPagerAdapter pagerAdapter;
    private SearchFilterAdapter searchFilterAdapter;

    private List<Category> categories = new ArrayList<>();
    private List<CharacterItem> characters = new ArrayList<>();
    private List<Category> searchFilters = new ArrayList<>();

    private AuthManager mAuth;
    private LocalDatabaseHelper localDb;

    private String baseUrl;
    private String selectedCategoryId;
    private final ExecutorService executor = new SafeExecutor();
    private final ExecutorService rewardExecutor = new SafeExecutor();
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    private boolean isSearching = false;
    private String selectedSearchFilterId = null;
    private List<CharacterItem> allSearchResults = new ArrayList<>();
    private static final int PAGE_SIZE = 1;
    private int charactersOffset = 0;
    private boolean hasMoreCharacters = true;
    private boolean isLoadingMore = false;

    private final Handler searchHandler = new Handler(Looper.getMainLooper());
    private Runnable searchRunnable;
    private final Runnable loadingSafetyTimeout = () -> hideLoadingOverlay();

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater, @Nullable ViewGroup container, @Nullable Bundle savedInstanceState) {
        return inflater.inflate(R.layout.fragment_home, container, false);
    }

    @Override
    public void onViewCreated(@NonNull View view, @Nullable Bundle savedInstanceState) {
        super.onViewCreated(view, savedInstanceState);

        ChatApplication app = (ChatApplication) requireActivity().getApplication();
        baseUrl = app.getPrefs().getServerUrl();
        mAuth = app.getAuthManager();
        localDb = new LocalDatabaseHelper(requireContext());

        charactersPager = view.findViewById(R.id.characters_pager);
        charactersPager.setOrientation(ViewPager2.ORIENTATION_VERTICAL);
        charactersPager.setUserInputEnabled(true);
        charactersPager.setOffscreenPageLimit(2);
        searchBar = view.findViewById(R.id.search_bar);
        searchProgress = view.findViewById(R.id.search_progress);
        emptyState = view.findViewById(R.id.empty_state);
        emptyStateTitle = view.findViewById(R.id.empty_state_title);
        emptyStateSubtitle = view.findViewById(R.id.empty_state_subtitle);
        searchFiltersRecycler = view.findViewById(R.id.search_filters_recycler);

        pagerAdapter = new CharacterPagerAdapter(characters, new CharacterPagerAdapter.OnPageClickListener() {
            @Override
            public void onCharacterClick(CharacterItem character) {
                openCharacterDetail(character);
            }

            @Override
            public void onFavoriteClick(CharacterItem character, boolean isFavorite) {
                toggleFavorite(character, isFavorite);
            }
        });
        charactersPager.setAdapter(pagerAdapter);

        charactersPager.registerOnPageChangeCallback(new ViewPager2.OnPageChangeCallback() {
            @Override
            public void onPageSelected(int position) {
                final int pos = position;
                charactersPager.post(() -> {
                    if (!isAdded()) return;
                    if (!isSearching && hasMoreCharacters && !isLoadingMore) {
                        if (pos >= characters.size() - 2) {
                            isLoadingMore = true;
                            pagerAdapter.setShowLoading(true);
                            loadCharactersPage(selectedCategoryId, charactersOffset, false);
                        }
                    }
                });
            }
        });

        searchFiltersRecycler.setLayoutManager(new LinearLayoutManager(getContext(), LinearLayoutManager.HORIZONTAL, false));
        searchFilterAdapter = new SearchFilterAdapter(searchFilters, filter -> {
            if (filter.id != null) {
                Category full = findCategoryById(filter.id);
                if (full != null && full.locked && full.mvcCost > 0) {
                    showUnlockDialog(full);
                    return;
                }
            }
            selectedSearchFilterId = filter.id;
            applySearchFilter();
        });
        searchFiltersRecycler.setAdapter(searchFilterAdapter);

        rewardIndicator = view.findViewById(R.id.reward_indicator);
        rewardIndicator.setOnClickListener(v -> {
            Intent intent = new Intent(getActivity(), MvcEarnActivity.class);
            startActivity(intent);
        });
        loadRewardIndicator();

        searchBar.addTextChangedListener(new TextWatcher() {
            @Override
            public void beforeTextChanged(CharSequence s, int start, int count, int after) {}

            @Override
            public void onTextChanged(CharSequence s, int start, int before, int count) {}

            @Override
            public void afterTextChanged(Editable s) {
                String query = s.toString().trim();
                if (searchRunnable != null) {
                    searchHandler.removeCallbacks(searchRunnable);
                }
                if (query.isEmpty()) {
                    isSearching = false;
                    selectedSearchFilterId = null;
                    searchFiltersRecycler.setVisibility(View.GONE);
                    if (selectedCategoryId != null) {
                        loadCharacters(selectedCategoryId);
                    }
                } else {
                    searchRunnable = () -> {
                        isSearching = true;
                        showSearchLoading();
                        searchCharacters(query);
                    };
                    searchHandler.postDelayed(searchRunnable, 300);
                }
            }
        });

        if (Cache.categories != null && !Cache.categories.isEmpty()) {
            categories.clear();
            categories.addAll(Cache.categories);
            selectedCategoryId = Cache.selectedCategoryId;
            if (selectedCategoryId != null) {
                for (int i = 0; i < categories.size(); i++) {
                    if (categories.get(i).id.equals(selectedCategoryId)) {
                        break;
                    }
                }
            }
            if (Cache.characters != null) {
                characters.clear();
                characters.addAll(Cache.characters);
                pagerAdapter.notifyDataSetChanged();
            }
            hideLoadingOverlay();
        } else {
            showLoadingOverlay("Caricamento categorie…");
        }
        loadCategories();
    }

    @Override
    public void onResume() {
        super.onResume();
        loadRewardIndicator();
    }

    private void loadRewardIndicator() {
        if (rewardIndicator == null) return;
        rewardExecutor.execute(() -> {
            try {
                String json = httpGetWithAuthRefresh(baseUrl + "/user/mevacoins/streak");
                if (json == null) {
                    mainHandler.post(() -> rewardIndicator.setText("Guadagna MVC"));
                    return;
                }
                JSONObject data = new JSONObject(json);
                int currentDay = data.optInt("current_day", 1);
                JSONArray days = data.optJSONArray("days");
                int nextReward = 10;
                if (days != null && currentDay <= days.length()) {
                    JSONObject today = days.getJSONObject(currentDay - 1);
                    nextReward = today.optInt("reward", 10);
                }
                boolean todayClaimed = false;
                if (days != null && currentDay <= days.length()) {
                    JSONObject today = days.getJSONObject(currentDay - 1);
                    todayClaimed = "claimed".equals(today.optString("status"));
                }
                final int day = currentDay;
                final int reward = nextReward;
                final boolean claimed = todayClaimed;
                mainHandler.post(() -> {
                    if (claimed) {
                        rewardIndicator.setText("\u2713 G" + day + " +" + reward);
                    } else {
                        rewardIndicator.setText("\uD83D\uDD25 G" + day + " +" + reward);
                    }
                });
            } catch (Exception e) {
                mainHandler.post(() -> rewardIndicator.setText("Guadagna MVC"));
            }
        });
    }

    private void refreshData() {
        if (isSearching) {
            String q = searchBar.getText().toString().trim();
            searchCharacters(q);
        } else {
            loadCategories();
        }
    }

    private void loadCategories() {
        executor.execute(() -> {
            try {
                String json = httpGetWithAuthRefresh(baseUrl + "/categories");
                if (json == null) {
                    mainHandler.post(() -> {
                        loadOfflineCategories();
                        hideLoadingOverlay();
                    });
                    return;
                }
            JSONArray arr = new JSONArray(json);
            List<Category> list = new ArrayList<>();
            Category perTeCategory = null;
            for (int i = 0; i < arr.length(); i++) {
                JSONObject obj = arr.getJSONObject(i);
                String id = obj.optString("id");
                Category cat = new Category(
                    id,
                    obj.optString("name"),
                    obj.optString("icon", "\uD83D\uDCCC"),
                    obj.optBoolean("premium", false),
                    obj.optBoolean("locked", false),
                    obj.optInt("mvc_cost", 0)
                );
                if ("per_te".equals(id)) {
                    perTeCategory = cat;
                } else {
                    list.add(cat);
                }
            }
            if (perTeCategory != null) {
                list.add(0, perTeCategory);
            }
                mainHandler.post(() -> {
                    categories.clear();
                    categories.addAll(list);
                    Cache.categories = new ArrayList<>(list);
                    updateLoadingProgress(1, 2, "Caricamento categorie…");

                    if (!categories.isEmpty()) {
                        selectedCategoryId = categories.get(0).id;
                        Cache.selectedCategoryId = selectedCategoryId;
                        loadCharacters(selectedCategoryId);
                    } else {
                        hideLoadingOverlay();
                    }
                });
            } catch (Exception e) {
                mainHandler.post(() -> {
                    loadOfflineCategories();
                    hideLoadingOverlay();
                });
            }
        });
    }

    private void loadOfflineCategories() {
        categories.clear();
        categories.add(new Category("romance", "Romantici", "\uD83D\uDC95"));
        categories.add(new Category("fantasy", "Fantasy", "\uD83E\uDDD9"));
        categories.add(new Category("anime", "Anime", "\uD83C\uDFB5"));
        categories.add(new Category("games", "Videogiochi", "\uD83C\uDFAE"));
        categories.add(new Category("history", "Storici", "\uD83C\uDFDB\uFE0F"));
        categories.add(new Category("scifi", "Fantascienza", "\uD83D\uDE80"));
        categories.add(new Category("horror", "Horror", "\uD83D\uDC7B"));
        categories.add(new Category("mystery", "Mistero", "\uD83D\uDD75\uFE0F"));
        Cache.categories = new ArrayList<>(categories);
        if (!categories.isEmpty()) {
            selectedCategoryId = categories.get(0).id;
            Cache.selectedCategoryId = selectedCategoryId;
        }
        loadOfflineCharacters();
    }

    private void loadCharacters(String categoryId) {
        charactersOffset = 0;
        hasMoreCharacters = true;
        isLoadingMore = false;
        characters.clear();
        charactersPager.post(() -> {
            if (!isAdded()) return;
            pagerAdapter.setShowLoading(false);
            pagerAdapter.notifyDataSetChanged();
        });
        hideEmptyState();
        loadCharactersPage(categoryId, 0, true);
    }

    private void loadCharactersPage(String categoryId, int offset, boolean initial) {
        if (initial) {
            charactersPager.post(() -> {
                if (!isAdded()) return;
                searchProgress.setVisibility(View.VISIBLE);
                showLoadingOverlay("Caricamento personaggi…");
                updateLoadingProgress(2, 3, "Caricamento personaggi…");
            });
        }
        executor.execute(() -> {
            try {
                String url = baseUrl + "/characters?category=" + URLEncoder.encode(categoryId, "UTF-8")
                    + "&limit=" + PAGE_SIZE + "&offset=" + offset;
                String json = httpGetWithAuthRefresh(url);
                List<CharacterItem> list = new ArrayList<>();
                if (json != null) {
                    JSONArray arr = new JSONArray(json);
                    for (int i = 0; i < arr.length(); i++) {
                        list.add(CharacterItem.fromJson(arr.getJSONObject(i)));
                    }
                }
                if (initial) {
                    ChatApplication app = (ChatApplication) requireActivity().getApplication();
                    JSONArray localChars = app.getLocalDb().getAllUserCharacters();
                    for (int i = 0; i < localChars.length(); i++) {
                        JSONObject lc = localChars.getJSONObject(i);
                        if (lc.optString("category", "").equals(categoryId)) {
                            list.add(CharacterItem.fromJson(lc));
                        }
                    }
                }
                final boolean hasMore = list.size() >= PAGE_SIZE;
                charactersPager.post(() -> {
                    if (!isAdded()) return;
                    searchProgress.setVisibility(View.GONE);
                    if (initial) {
                        characters.clear();
                    }
                    java.util.Set<String> existingIds = new java.util.HashSet<>();
                    for (CharacterItem c : characters) {
                        existingIds.add(c.id);
                    }
                    for (CharacterItem c : list) {
                        if (!existingIds.contains(c.id)) {
                            characters.add(c);
                            existingIds.add(c.id);
                        }
                    }
                    hasMoreCharacters = hasMore;
                    charactersOffset = offset + list.size();
                    isLoadingMore = false;
                    pagerAdapter.setShowLoading(false);
                    Cache.characters = new ArrayList<>(characters);
                    pagerAdapter.notifyDataSetChanged();
                    charactersPager.setVisibility(View.VISIBLE);
                    if (initial) {
                        updateLoadingProgress(3, 3, "Caricamento completato");
                        hideLoadingOverlay();
                    }
                    if (characters.isEmpty()) {
                        emptyState.setVisibility(View.VISIBLE);
                        emptyStateTitle.setText("Nessun personaggio");
                        emptyStateSubtitle.setText("Prova un'altra categoria");
                    }
                });
            } catch (Exception e) {
                charactersPager.post(() -> {
                    if (!isAdded()) return;
                    searchProgress.setVisibility(View.GONE);
                    if (initial) {
                        loadOfflineCharacters();
                        hideLoadingOverlay();
                    }
                    isLoadingMore = false;
                    pagerAdapter.setShowLoading(false);
                });
            }
        });
    }

    private void loadOfflineCharacters() {
        characters.clear();
        characters.add(new CharacterItem("ginecologa", "Dottoressa", "\uD83D\uDC69\u200D\u2695\uFE0F", null,
            "Una professionista pronta ad ascoltarti", new String[]{"medico", "professionale"},
            15420, "romance"));
        characters.add(new CharacterItem("infermiera", "Infermiera", "\uD83D\uDC69\u200D\uD83C\uDF93", null,
            "Dolce e premurosa, sempre al tuo fianco", new String[]{"cura", "dolcezza"},
            8930, "romance"));
        characters.add(new CharacterItem("maga", "Maga Serena", "\uD83E\uDDD9\u200D\u2640\uFE0F", null,
            "Potente maga con un cuore d'oro", new String[]{"magia", "fantasy"},
            12500, "fantasy"));
        characters.add(new CharacterItem("cavaliere", "Cavaliere Oscuro", "\uD83D\uDEE1\uFE0F", null,
            "Protettore delle terre dimenticate", new String[]{"cavaliere", "epico"},
            7600, "fantasy"));
        Cache.characters = new ArrayList<>(characters);
        pagerAdapter.notifyDataSetChanged();
    }

    private void searchCharacters(String query) {
        executor.execute(() -> {
            try {
                String encoded = URLEncoder.encode(query, "UTF-8");
                String json = httpGetWithAuthRefresh(baseUrl + "/characters/search?q=" + encoded);
                if (json == null) {
                    mainHandler.post(() -> {
                        hideSearchLoading();
                        showEmptyState("Nessun personaggio trovato", "Prova con un'altra ricerca");
                    });
                    return;
                }
                JSONArray arr = new JSONArray(json);
                List<CharacterItem> list = new ArrayList<>();
                for (int i = 0; i < arr.length(); i++) {
                    list.add(CharacterItem.fromJson(arr.getJSONObject(i)));
                }
                allSearchResults.clear();
                allSearchResults.addAll(list);
                mainHandler.post(() -> {
                    hideSearchLoading();
                    loadSearchFilters();
                    applySearchFilter();
                });
            } catch (Exception e) {
                mainHandler.post(() -> {
                    hideSearchLoading();
                    showEmptyState("Nessun personaggio trovato", "Prova con un'altra ricerca");
                });
            }
        });
    }

    private void loadSearchFilters() {
        searchFilters.clear();
        Category allFilter = new Category(null, "Tutti", "📋");
        searchFilters.add(allFilter);

        java.util.Map<String, String> categoryNames = new java.util.HashMap<>();
        for (Category cat : categories) {
            categoryNames.put(cat.id, cat.icon + " " + cat.name);
        }

        java.util.Set<String> seenCategories = new java.util.LinkedHashSet<>();
        for (CharacterItem item : allSearchResults) {
            if (item.category != null && !item.category.isEmpty() && !seenCategories.contains(item.category)) {
                seenCategories.add(item.category);
                String displayName = categoryNames.getOrDefault(item.category, item.category);
                searchFilters.add(new Category(item.category, displayName, ""));
            }
        }

        selectedSearchFilterId = null;
        searchFilterAdapter.setSelected(0);
        searchFiltersRecycler.setVisibility(View.GONE);
        searchFilterAdapter.notifyDataSetChanged();
    }

    private void applySearchFilter() {
        List<CharacterItem> filtered;
        if (selectedSearchFilterId == null) {
            filtered = new ArrayList<>(allSearchResults);
        } else {
            filtered = new ArrayList<>();
            for (CharacterItem item : allSearchResults) {
                if (selectedSearchFilterId.equals(item.category)) {
                    filtered.add(item);
                }
            }
        }

        characters.clear();
        characters.addAll(filtered);
        pagerAdapter.setShowLoading(false);
        pagerAdapter.notifyDataSetChanged();

        if (filtered.isEmpty()) {
            showEmptyState("Nessun risultato per questo filtro", "Prova con un altro filtro");
        } else {
            hideEmptyState();
        }
    }

    private void showSearchLoading() {
        searchProgress.setVisibility(View.VISIBLE);
        charactersPager.setVisibility(View.GONE);
        emptyState.setVisibility(View.GONE);
    }

    private void hideSearchLoading() {
        searchProgress.setVisibility(View.GONE);
        charactersPager.setVisibility(View.VISIBLE);
    }

    private void showLoadingOverlay(String message) {
        if (getActivity() instanceof MainActivity) {
            ((MainActivity) getActivity()).showLoading(message);
            mainHandler.removeCallbacks(loadingSafetyTimeout);
            mainHandler.postDelayed(loadingSafetyTimeout, 15000);
        }
    }

    private void updateLoadingProgress(int current, int total, String phase) {
        if (getActivity() instanceof MainActivity) {
            ((MainActivity) getActivity()).updateLoadingProgress(current, total, phase);
        }
    }

    private void hideLoadingOverlay() {
        mainHandler.removeCallbacks(loadingSafetyTimeout);
        if (getActivity() instanceof MainActivity) {
            ((MainActivity) getActivity()).hideLoading();
        }
    }

    private void showEmptyState(String title, String subtitle) {
        emptyState.setVisibility(View.VISIBLE);
        charactersPager.setVisibility(View.GONE);
        emptyStateTitle.setText(title);
        emptyStateSubtitle.setText(subtitle);
    }

    private void hideEmptyState() {
        emptyState.setVisibility(View.GONE);
        charactersPager.setVisibility(View.VISIBLE);
    }

    private void toggleFavorite(CharacterItem character, boolean isFavorite) {
        executor.execute(() -> {
            try {
                if (isFavorite) {
                    localDb.addFavorite(character.id);
                } else {
                    localDb.removeFavorite(character.id);
                }
            } catch (Exception e) {
                mainHandler.post(() -> showSnackbar("Errore nel salvare il preferito"));
            }
        });
    }

    private void openCharacterDetail(CharacterItem character) {
        Intent intent = new Intent(getActivity(), CharacterDetailActivity.class);
        intent.putExtra("character_id", character.id);
        startActivity(intent);
    }

    private void unlockCategory(Category category) {
        executor.execute(() -> {
            try {
                JSONObject body = new JSONObject();
                body.put("content_type", "category");
                body.put("content_id", category.id);
                body.put("amount", category.mvcCost);
                AuthManager.HttpResponse httpResp = mAuth.requestWithRefresh(baseUrl + "/user/mevacoins/spend", "POST", body.toString(), 8000);
                if (httpResp.statusCode != 200) {
                    mainHandler.post(() -> showSnackbar("Errore nello sblocco"));
                    return;
                }
                JSONObject obj = new JSONObject(httpResp.body);
                if (obj.optBoolean("unlocked", false)) {
                    mainHandler.post(() -> {
                        showSnackbar("Categoria sbloccata!");
                        refreshData();
                    });
                } else {
                    mainHandler.post(() -> showSnackbar("MVC insufficienti"));
                }
            } catch (Exception e) {
                mainHandler.post(() -> showSnackbar("Errore: " + e.getMessage()));
            }
        });
    }

    private Category findCategoryById(String id) {
        if (id == null) return null;
        for (Category c : categories) {
            if (id.equals(c.id)) return c;
        }
        return null;
    }

    private void showUnlockDialog(Category cat) {
        executor.execute(() -> {
            final int balance = fetchBalance();
            mainHandler.post(() -> {
                if (!isAdded() || getContext() == null) return;
                AlertDialog.Builder builder = new AlertDialog.Builder(requireContext());
                builder.setTitle(cat.icon + " " + cat.name);
                if (balance < cat.mvcCost) {
                    builder.setMessage("Servono " + cat.mvcCost + " MVC per sbloccare questa categoria.\nHai " + balance + " MVC.");
                    builder.setPositiveButton("Guadagna MVC", (d, w) -> {
                        Intent intent = new Intent(getActivity(), MvcEarnActivity.class);
                        startActivity(intent);
                    });
                    builder.setNegativeButton("Annulla", null);
                } else {
                    builder.setMessage("Sbloccare questa categoria per " + cat.mvcCost + " MVC?\nHai " + balance + " MVC.");
                    builder.setPositiveButton("Sblocca", (d, w) -> unlockCategory(cat));
                    builder.setNegativeButton("Annulla", null);
                }
                builder.show();
            });
        });
    }

    private int fetchBalance() {
        try {
            AuthManager.HttpResponse resp = mAuth.requestWithRefresh(baseUrl + "/user/mevacoins", "GET", null, 10000);
            if (resp.statusCode == 200 && resp.body != null) {
                JSONObject obj = new JSONObject(resp.body);
                return obj.optInt("balance", 0);
            }
        } catch (Exception ignored) {
        }
        return 0;
    }

    private void showSnackbar(String msg) {
        Snackbar.make(requireView(), msg, Snackbar.LENGTH_SHORT).show();
    }

    private String httpGet(String urlString) {
        return httpGetWithAuth(urlString);
    }

    private String httpGetWithAuth(String urlString) {
        HttpURLConnection conn = null;
        try {
            URL url = new URL(urlString);
            conn = (HttpURLConnection) url.openConnection();
            conn.setConnectTimeout(8000);
            conn.setReadTimeout(8000);
            conn.setRequestProperty("Accept", "application/json");
            if (mAuth.isLoggedIn()) {
                conn.setRequestProperty("Authorization", "Bearer " + mAuth.getAccessToken());
            }
            int code = conn.getResponseCode();
            if (code != 200) return null;
            BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()));
            StringBuilder response = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) {
                response.append(line);
            }
            reader.close();
            return response.toString();
        } catch (Exception e) {
            return null;
        } finally {
            if (conn != null) conn.disconnect();
        }
    }

    private String httpGetWithAuthRefresh(String urlString) {
        try {
            AuthManager.HttpResponse resp = mAuth.requestWithRefresh(urlString, "GET", null, 15000);
            if (resp.statusCode == 200) {
                return resp.body;
            }
        } catch (Exception e) {
            return null;
        }
        return null;
    }

    private String httpPostWithAuth(String urlString, String jsonBody) {
        HttpURLConnection conn = null;
        try {
            URL url = new URL(urlString);
            conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("POST");
            conn.setDoOutput(true);
            conn.setConnectTimeout(8000);
            conn.setReadTimeout(8000);
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setRequestProperty("Accept", "application/json");
            if (mAuth.isLoggedIn()) {
                conn.setRequestProperty("Authorization", "Bearer " + mAuth.getAccessToken());
            }
            java.io.OutputStream os = conn.getOutputStream();
            os.write(jsonBody.getBytes("UTF-8"));
            os.close();
            int code = conn.getResponseCode();
            java.io.InputStream is;
            if (code < 400) {
                is = conn.getInputStream();
            } else {
                is = conn.getErrorStream();
                if (is == null) is = conn.getInputStream();
            }
            BufferedReader reader = new BufferedReader(new InputStreamReader(
                is != null ? is : new java.io.ByteArrayInputStream(new byte[0])));
            StringBuilder response = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) {
                response.append(line);
            }
            reader.close();
            if (code >= 400) return null;
            return response.toString();
        } catch (Exception e) {
            return null;
        } finally {
            if (conn != null) conn.disconnect();
        }
    }

    @Override
    public void onDestroy() {
        super.onDestroy();
        executor.shutdown();
        rewardExecutor.shutdown();
    }

    public static class Category {
        public final String id;
        public final String name;
        public final String icon;
        public final boolean premium;
        public final boolean locked;
        public final int mvcCost;

        public Category(String id, String name, String icon) {
            this(id, name, icon, false, false, 0);
        }

        public Category(String id, String name, String icon, boolean premium, boolean locked, int mvcCost) {
            this.id = id;
            this.name = name;
            this.icon = icon;
            this.premium = premium;
            this.locked = locked;
            this.mvcCost = mvcCost;
        }
    }

    public static class CharacterItem {
        public final String id;
        public final String name;
        public final String emoji;
        public final String avatarImage;
        public final String description;
        public final String[] tags;
        public final int conversationsCount;
        public final String category;
        public int intimacy = 0;
        public String intimacyLabel = "";

        public CharacterItem(String id, String name, String emoji, String avatarImage, String description,
                             String[] tags, int conversationsCount, String category) {
            this.id = id;
            this.name = name;
            this.emoji = emoji;
            this.avatarImage = avatarImage;
            this.description = description;
            this.tags = tags;
            this.conversationsCount = conversationsCount;
            this.category = category;
        }

        public static CharacterItem fromJson(JSONObject obj) {
            String id = obj.optString("id", "");
            String name = obj.optString("name", "");
            String emoji = obj.optString("avatar", "\uD83D\uDC64");
            String avatarImage = obj.optString("avatar_image", null);
            String description = obj.optString("description", "");
            JSONArray tagsArr = obj.optJSONArray("tags");
            String[] tags = new String[0];
            if (tagsArr != null) {
                tags = new String[tagsArr.length()];
                for (int i = 0; i < tagsArr.length(); i++) {
                    tags[i] = tagsArr.optString(i, "");
                }
            }
            int conversations = obj.optInt("conversations", 0);
            String category = obj.optString("category", "");
            CharacterItem item = new CharacterItem(id, name, emoji, avatarImage, description, tags, conversations, category);
            item.intimacy = obj.optInt("intimacy", 0);
            item.intimacyLabel = obj.optString("intimacy_label", "");
            return item;
        }

        public String getTagsString() {
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < tags.length; i++) {
                if (i > 0) sb.append(" · ");
                sb.append(tags[i]);
            }
            return sb.toString();
        }

        public String getConversationsString() {
            if (conversationsCount >= 1000000) {
                return String.format("%.1fM", conversationsCount / 1000000.0);
            } else if (conversationsCount >= 1000) {
                return String.format("%.1fK", conversationsCount / 1000.0);
            }
            return String.valueOf(conversationsCount);
        }
    }

    public static class SearchFilterAdapter extends RecyclerView.Adapter<SearchFilterAdapter.FilterViewHolder> {
        private final List<Category> filters;
        private final java.util.function.Consumer<Category> onFilterSelected;
        private int selectedPosition = 0;

        public SearchFilterAdapter(List<Category> filters, java.util.function.Consumer<Category> onFilterSelected) {
            this.filters = filters;
            this.onFilterSelected = onFilterSelected;
        }

        public void setSelected(int position) {
            int old = selectedPosition;
            selectedPosition = position;
            notifyItemChanged(old);
            notifyItemChanged(position);
        }

        @NonNull
        @Override
        public FilterViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
            View view = LayoutInflater.from(parent.getContext()).inflate(R.layout.item_search_filter, parent, false);
            return new FilterViewHolder(view);
        }

        @Override
        public void onBindViewHolder(@NonNull FilterViewHolder holder, int position) {
            Category filter = filters.get(position);
            holder.chip.setText(filter.name);
            holder.chip.setChecked(position == selectedPosition);
            holder.chip.setOnClickListener(v -> {
                setSelected(holder.getAdapterPosition());
                onFilterSelected.accept(filter);
            });
        }

        @Override
        public int getItemCount() {
            return filters.size();
        }

        static class FilterViewHolder extends RecyclerView.ViewHolder {
            final com.google.android.material.button.MaterialButton chip;

            FilterViewHolder(@NonNull View itemView) {
                super(itemView);
                chip = itemView.findViewById(R.id.filter_chip);
            }
        }
    }
}
