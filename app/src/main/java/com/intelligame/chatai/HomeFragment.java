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
import androidx.recyclerview.widget.LinearSnapHelper;
import androidx.recyclerview.widget.RecyclerView;
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout;

import com.google.android.material.floatingactionbutton.FloatingActionButton;

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

    private SwipeRefreshLayout swipeRefresh;
    private RecyclerView charactersRecycler;
    private EditText searchBar;
    private TextView sectionTitle;
    private FloatingActionButton fabScrollTop;
    private ProgressBar searchProgress;
    private LinearLayout emptyState;
    private TextView emptyStateTitle;
    private TextView emptyStateSubtitle;
    private RecyclerView searchFiltersRecycler;

    private CategoryAdapter categoryAdapter;
    private CharacterCardAdapter characterAdapter;
    private SearchFilterAdapter searchFilterAdapter;

    private List<Category> categories = new ArrayList<>();
    private List<CharacterItem> characters = new ArrayList<>();
    private List<Category> searchFilters = new ArrayList<>();

    private AuthManager mAuth;
    private LocalDatabaseHelper localDb;

    private String baseUrl;
    private String selectedCategoryId;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    private boolean isSearching = false;
    private String selectedSearchFilterId = null;
    private List<CharacterItem> allSearchResults = new ArrayList<>();

    private final Handler searchHandler = new Handler(Looper.getMainLooper());
    private Runnable searchRunnable;

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

        swipeRefresh = view.findViewById(R.id.swipe_refresh);
        charactersRecycler = view.findViewById(R.id.characters_recycler);
        searchBar = view.findViewById(R.id.search_bar);
        sectionTitle = view.findViewById(R.id.section_title);
        fabScrollTop = view.findViewById(R.id.fab_scroll_top);
        searchProgress = view.findViewById(R.id.search_progress);
        emptyState = view.findViewById(R.id.empty_state);
        emptyStateTitle = view.findViewById(R.id.empty_state_title);
        emptyStateSubtitle = view.findViewById(R.id.empty_state_subtitle);
        searchFiltersRecycler = view.findViewById(R.id.search_filters_recycler);

        swipeRefresh.setColorSchemeColors(getResources().getColor(R.color.primary));
        swipeRefresh.setProgressBackgroundColorSchemeColor(getResources().getColor(R.color.surface_container));
        swipeRefresh.setOnRefreshListener(this::refreshData);

        new LinearSnapHelper().attachToRecyclerView(charactersRecycler);

        charactersRecycler.addOnScrollListener(new RecyclerView.OnScrollListener() {
            @Override
            public void onScrolled(@NonNull RecyclerView rv, int dx, int dy) {
                if (rv.canScrollVertically(-1)) {
                    fabScrollTop.setVisibility(View.VISIBLE);
                } else {
                    fabScrollTop.setVisibility(View.GONE);
                }
            }
        });
        fabScrollTop.setOnClickListener(v -> charactersRecycler.smoothScrollToPosition(0));

        categoryAdapter = new CategoryAdapter(categories, category -> {
            if (category.locked) {
                new AlertDialog.Builder(requireContext())
                    .setTitle("\uD83D\uDD12 Categoria bloccata")
                    .setMessage("Sblocca la categoria " + category.name + " con " + category.mvcCost + " MVC per accedere ai personaggi.")
                    .setPositiveButton("Sblocca (" + category.mvcCost + " MVC)", (dialog, which) -> unlockCategory(category))
                    .setNegativeButton("Annulla", null)
                    .show();
                return;
            }
            selectedCategoryId = category.id;
            isSearching = false;
            searchBar.setText("");
            loadCharacters(category.id);
        });

        boolean ageVerified = app.getPrefs().getAdultBirthYear() > 0;

        characterAdapter = new CharacterCardAdapter(characters, character -> {
            if (character.isAdult && !ageVerified) {
                AdultConfirmDialog dialog = new AdultConfirmDialog(() -> openCharacterDetail(character));
                dialog.show(getParentFragmentManager(), "adult_confirm");
            } else {
                openCharacterDetail(character);
            }
        }, (character, isFavorite) -> toggleFavorite(character, isFavorite), true);
        charactersRecycler.setAdapter(characterAdapter);

        searchFiltersRecycler.setLayoutManager(new LinearLayoutManager(getContext(), LinearLayoutManager.HORIZONTAL, false));
        searchFilterAdapter = new SearchFilterAdapter(searchFilters, filter -> {
            selectedSearchFilterId = filter.id;
            applySearchFilter();
        });
        searchFiltersRecycler.setAdapter(searchFilterAdapter);

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
            categoryAdapter.notifyDataSetChanged();
            selectedCategoryId = Cache.selectedCategoryId;
            if (selectedCategoryId != null) {
                for (int i = 0; i < categories.size(); i++) {
                    if (categories.get(i).id.equals(selectedCategoryId)) {
                        categoryAdapter.setSelected(i);
                        break;
                    }
                }
            }
            if (Cache.characters != null) {
                characters.clear();
                characters.addAll(Cache.characters);
                characterAdapter.notifyDataSetChanged();
            }
            hideLoadingOverlay();
        } else {
            showLoadingOverlay("Caricamento categorie…");
        }
        loadCategories();
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
                String json = httpGetWithAuth(baseUrl + "/categories");
                if (json == null) {
                    mainHandler.post(() -> {
                        swipeRefresh.setRefreshing(false);
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
                final int totalCategories = list.size();
                mainHandler.post(() -> {
                    categories.clear();
                    categories.addAll(list);
                    Cache.categories = new ArrayList<>(list);
                    categoryAdapter.notifyDataSetChanged();
                    swipeRefresh.setRefreshing(false);
                    updateLoadingProgress(1, totalCategories);

                    if (!categories.isEmpty()) {
                        selectedCategoryId = categories.get(0).id;
                        Cache.selectedCategoryId = selectedCategoryId;
                        categoryAdapter.setSelected(0);
                        loadCharacters(selectedCategoryId);
                    } else {
                        hideLoadingOverlay();
                    }
                });
            } catch (Exception e) {
                mainHandler.post(() -> {
                    swipeRefresh.setRefreshing(false);
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
        categoryAdapter.notifyDataSetChanged();
        if (!categories.isEmpty()) {
            selectedCategoryId = categories.get(0).id;
            Cache.selectedCategoryId = selectedCategoryId;
            categoryAdapter.setSelected(0);
        }
        loadOfflineCharacters();
        swipeRefresh.setRefreshing(false);
    }

    private void loadCharacters(String categoryId) {
        mainHandler.post(() -> {
            searchProgress.setVisibility(View.VISIBLE);
            showLoadingOverlay("Caricamento personaggi…");
        });
        executor.execute(() -> {
            try {
                String json = httpGet(baseUrl + "/characters?category=" + URLEncoder.encode(categoryId, "UTF-8"));
                List<CharacterItem> list = new ArrayList<>();
                if (json != null) {
                    JSONArray arr = new JSONArray(json);
                    for (int i = 0; i < arr.length(); i++) {
                        list.add(CharacterItem.fromJson(arr.getJSONObject(i)));
                    }
                }
                ChatApplication app = (ChatApplication) requireActivity().getApplication();
                JSONArray localChars = app.getLocalDb().getAllUserCharacters();
                for (int i = 0; i < localChars.length(); i++) {
                    JSONObject lc = localChars.getJSONObject(i);
                    if (lc.optString("category", "").equals(categoryId)) {
                        list.add(CharacterItem.fromJson(lc));
                    }
                }
                mainHandler.post(() -> {
                    searchProgress.setVisibility(View.GONE);
                    characters.clear();
                    characters.addAll(list);
                    Cache.characters = new ArrayList<>(list);
                    characterAdapter.notifyDataSetChanged();
                    sectionTitle.setText("Personaggi");
                    hideLoadingOverlay();
                });
            } catch (Exception e) {
                mainHandler.post(() -> {
                    searchProgress.setVisibility(View.GONE);
                    loadOfflineCharacters();
                    hideLoadingOverlay();
                });
            }
        });
    }

    private void loadOfflineCharacters() {
        characters.clear();
        characters.add(new CharacterItem("ginecologa", "Dottoressa", "\uD83D\uDC69\u200D\u2695\uFE0F", null,
            "Una professionista pronta ad ascoltarti", new String[]{"medico", "professionale"},
            15420, "romance", false));
        characters.add(new CharacterItem("infermiera", "Infermiera", "\uD83D\uDC69\u200D\uD83C\uDF93", null,
            "Dolce e premurosa, sempre al tuo fianco", new String[]{"cura", "dolcezza"},
            8930, "romance", false));
        characters.add(new CharacterItem("maga", "Maga Serena", "\uD83E\uDDD9\u200D\u2640\uFE0F", null,
            "Potente maga con un cuore d'oro", new String[]{"magia", "fantasy"},
            12500, "fantasy", false));
        characters.add(new CharacterItem("cavaliere", "Cavaliere Oscuro", "\uD83D\uDEE1\uFE0F", null,
            "Protettore delle terre dimenticate", new String[]{"cavaliere", "epico"},
            7600, "fantasy", false));
        Cache.characters = new ArrayList<>(characters);
        characterAdapter.notifyDataSetChanged();
        sectionTitle.setText("Personaggi");
    }

    private void searchCharacters(String query) {
        executor.execute(() -> {
            try {
                String encoded = URLEncoder.encode(query, "UTF-8");
                String json = httpGet(baseUrl + "/characters/search?q=" + encoded);
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
        searchFiltersRecycler.setVisibility(searchFilters.size() > 1 ? View.VISIBLE : View.GONE);
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
        characterAdapter.notifyDataSetChanged();

        if (filtered.isEmpty()) {
            showEmptyState("Nessun risultato per questo filtro", "Prova con un altro filtro");
        } else {
            hideEmptyState();
            sectionTitle.setText("Risultati: " + filtered.size());
        }
    }

    private void showSearchLoading() {
        searchProgress.setVisibility(View.VISIBLE);
        charactersRecycler.setVisibility(View.GONE);
        emptyState.setVisibility(View.GONE);
        sectionTitle.setText("Ricerca...");
    }

    private void hideSearchLoading() {
        searchProgress.setVisibility(View.GONE);
        charactersRecycler.setVisibility(View.VISIBLE);
    }

    private void showLoadingOverlay(String message) {
        if (getActivity() instanceof MainActivity) {
            ((MainActivity) getActivity()).showLoading(message);
        }
    }

    private void updateLoadingProgress(int current, int total) {
        if (getActivity() instanceof MainActivity) {
            ((MainActivity) getActivity()).showLoadingProgress(current, total);
        }
    }

    private void hideLoadingOverlay() {
        if (getActivity() instanceof MainActivity) {
            ((MainActivity) getActivity()).hideLoading();
        }
    }

    private void showEmptyState(String title, String subtitle) {
        emptyState.setVisibility(View.VISIBLE);
        charactersRecycler.setVisibility(View.GONE);
        emptyStateTitle.setText(title);
        emptyStateSubtitle.setText(subtitle);
        sectionTitle.setText("");
    }

    private void hideEmptyState() {
        emptyState.setVisibility(View.GONE);
        charactersRecycler.setVisibility(View.VISIBLE);
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
                String resp = httpPostWithAuth(baseUrl + "/user/mevacoins/spend", body.toString());
                if (resp == null) {
                    mainHandler.post(() -> showSnackbar("Errore nello sblocco"));
                    return;
                }
                JSONObject obj = new JSONObject(resp);
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

    private void showSnackbar(String msg) {
        com.google.android.material.snackbar.Snackbar.make(requireView(), msg, com.google.android.material.snackbar.Snackbar.LENGTH_SHORT).show();
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
            BufferedReader reader = new BufferedReader(new InputStreamReader(
                code >= 400 ? conn.getErrorStream() : conn.getInputStream()));
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
        public final boolean isAdult;

        public CharacterItem(String id, String name, String emoji, String avatarImage, String description,
                             String[] tags, int conversationsCount, String category, boolean isAdult) {
            this.id = id;
            this.name = name;
            this.emoji = emoji;
            this.avatarImage = avatarImage;
            this.description = description;
            this.tags = tags;
            this.conversationsCount = conversationsCount;
            this.category = category;
            this.isAdult = isAdult;
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
            boolean isAdult = obj.optBoolean("is_adult", false);
            return new CharacterItem(id, name, emoji, avatarImage, description, tags, conversations, category, isAdult);
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