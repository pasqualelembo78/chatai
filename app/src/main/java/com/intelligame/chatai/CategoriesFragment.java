package com.intelligame.chatai;

import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ProgressBar;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.Fragment;
import androidx.recyclerview.widget.GridLayoutManager;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class CategoriesFragment extends Fragment {

    private RecyclerView categoriesRecycler;
    private ProgressBar loadingProgress;
    private TextView backButton;
    private TextView titleText;

    private AuthManager mAuth;
    private String baseUrl;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    private List<HomeFragment.Category> categories = new ArrayList<>();
    private CategoryGridAdapter gridAdapter;

    private boolean showingCharacters = false;
    private List<HomeFragment.CharacterItem> currentCategoryCharacters = new ArrayList<>();
    private CharacterListAdapter listAdapter;

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater, @Nullable ViewGroup container, @Nullable Bundle savedInstanceState) {
        return inflater.inflate(R.layout.fragment_categories, container, false);
    }

    @Override
    public void onViewCreated(@NonNull View view, @Nullable Bundle savedInstanceState) {
        super.onViewCreated(view, savedInstanceState);

        ChatApplication app = (ChatApplication) requireActivity().getApplication();
        baseUrl = app.getPrefs().getServerUrl();
        mAuth = app.getAuthManager();

        categoriesRecycler = view.findViewById(R.id.categories_recycler);
        loadingProgress = view.findViewById(R.id.loading_progress);
        backButton = view.findViewById(R.id.back_button);
        titleText = view.findViewById(R.id.title_text);

        backButton.setOnClickListener(v -> {
            if (showingCharacters) {
                showCategoriesView();
            } else {
                requireActivity().onBackPressed();
            }
        });

        gridAdapter = new CategoryGridAdapter();
        categoriesRecycler.setLayoutManager(new GridLayoutManager(requireContext(), 2));
        categoriesRecycler.setAdapter(gridAdapter);

        listAdapter = new CharacterListAdapter();

        loadCategories();
    }

    private void loadCategories() {
        loadingProgress.setVisibility(View.VISIBLE);
        executor.execute(() -> {
            try {
                String json = httpGetWithAuthRefresh(baseUrl + "/categories");
                if (json != null) {
                    JSONArray arr = new JSONArray(json);
                    List<HomeFragment.Category> list = new ArrayList<>();
                    for (int i = 0; i < arr.length(); i++) {
                        JSONObject obj = arr.getJSONObject(i);
                        String id = obj.optString("id");
                        if ("per_te".equals(id)) continue;
                        list.add(new HomeFragment.Category(
                            id,
                            obj.optString("name"),
                            obj.optString("icon", "\uD83D\uDCCC"),
                            obj.optBoolean("premium", false),
                            obj.optBoolean("locked", false),
                            obj.optInt("mvc_cost", 0)
                        ));
                    }
                    mainHandler.post(() -> {
                        categories.clear();
                        categories.addAll(list);
                        gridAdapter.notifyDataSetChanged();
                        loadingProgress.setVisibility(View.GONE);
                    });
                } else {
                    mainHandler.post(() -> {
                        loadOfflineCategories();
                        loadingProgress.setVisibility(View.GONE);
                    });
                }
            } catch (Exception e) {
                mainHandler.post(() -> {
                    loadOfflineCategories();
                    loadingProgress.setVisibility(View.GONE);
                });
            }
        });
    }

    private void loadOfflineCategories() {
        categories.clear();
        categories.add(new HomeFragment.Category("romance", "Romantici", "\uD83D\uDC95"));
        categories.add(new HomeFragment.Category("fantasy", "Fantasy", "\uD83E\uDDD9"));
        categories.add(new HomeFragment.Category("anime", "Anime", "\uD83C\uDFB5"));
        categories.add(new HomeFragment.Category("gamer", "Videogiochi", "\uD83C\uDFAE"));
        categories.add(new HomeFragment.Category("storia", "Storici", "\uD83C\uDFDB\uFE0F"));
        categories.add(new HomeFragment.Category("sci_fi", "Fantascienza", "\uD83D\uDE80"));
        categories.add(new HomeFragment.Category("horror", "Horror", "\uD83D\uDC7B"));
        categories.add(new HomeFragment.Category("detective", "Mistero", "\uD83D\uDD75\uFE0F"));
        categories.add(new HomeFragment.Category("amicizia", "Amicizia", "\uD83E\uDD1D"));
        categories.add(new HomeFragment.Category("sport", "Sport", "\u26BD"));
        categories.add(new HomeFragment.Category("cucina", "Cucina", "\uD83C\uDF73"));
        categories.add(new HomeFragment.Category("medicina", "Medicina", "\uD83C\uDFE5"));
        categories.add(new HomeFragment.Category("tecnologia", "Tecnologia", "\uD83D\uDCBB"));
        categories.add(new HomeFragment.Category("creativi", "Creativi", "\uD83C\uDFA8"));
        categories.add(new HomeFragment.Category("relazioni", "Relazioni", "\uD83D\uDC91"));
        categories.add(new HomeFragment.Category("motivazione", "Motivazione", "\uD83D\uDCAA"));
        categories.add(new HomeFragment.Category("scuola", "Scuola", "\uD83C\uDF93"));
        categories.add(new HomeFragment.Category("viaggi", "Viaggi", "\uD83D\uDEE2\uFE0F"));
        categories.add(new HomeFragment.Category("seduzione", "Seduzione", "\uD83D\uDE08"));
        categories.add(new HomeFragment.Category("sopravvivenza", "Sopravvivenza", "\uD83C\uDFD4\uFE0F"));
        categories.add(new HomeFragment.Category("business", "Business", "\uD83D\uDCBC"));
        categories.add(new HomeFragment.Category("premium", "Premium", "\uD83D\uDC8E"));
        gridAdapter.notifyDataSetChanged();
    }

    private void loadCharactersForCategory(String categoryId) {
        showingCharacters = true;
        titleText.setText(categories.stream()
            .filter(c -> c.id.equals(categoryId))
            .map(c -> c.icon + " " + c.name)
            .findFirst()
            .orElse("Personaggi"));
        backButton.setText("←");

        currentCategoryCharacters.clear();
        listAdapter.notifyDataSetChanged();
        categoriesRecycler.setLayoutManager(new LinearLayoutManager(requireContext()));
        categoriesRecycler.setAdapter(listAdapter);
        loadingProgress.setVisibility(View.VISIBLE);

        executor.execute(() -> {
            try {
                String url = baseUrl + "/characters?category=" + categoryId + "&limit=100&offset=0";
                String json = httpGetWithAuthRefresh(url);
                if (json != null) {
                    JSONArray arr = new JSONArray(json);
                    List<HomeFragment.CharacterItem> list = new ArrayList<>();
                    for (int i = 0; i < arr.length(); i++) {
                        list.add(HomeFragment.CharacterItem.fromJson(arr.getJSONObject(i)));
                    }
                    mainHandler.post(() -> {
                        currentCategoryCharacters.clear();
                        currentCategoryCharacters.addAll(list);
                        listAdapter.notifyDataSetChanged();
                        loadingProgress.setVisibility(View.GONE);
                    });
                } else {
                    mainHandler.post(() -> loadingProgress.setVisibility(View.GONE));
                }
            } catch (Exception e) {
                mainHandler.post(() -> loadingProgress.setVisibility(View.GONE));
            }
        });
    }

    private void showCategoriesView() {
        showingCharacters = false;
        titleText.setText("Categorie");
        backButton.setText("←");
        categoriesRecycler.setLayoutManager(new GridLayoutManager(requireContext(), 2));
        categoriesRecycler.setAdapter(gridAdapter);
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

    @Override
    public void onDestroy() {
        super.onDestroy();
        executor.shutdown();
    }

    // ─── Category Grid Adapter ─────────────────────────────────────

    class CategoryGridAdapter extends RecyclerView.Adapter<CategoryGridAdapter.VH> {

        @NonNull
        @Override
        public VH onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
            View v = LayoutInflater.from(parent.getContext()).inflate(R.layout.item_category_grid, parent, false);
            return new VH(v);
        }

        @Override
        public void onBindViewHolder(@NonNull VH holder, int position) {
            HomeFragment.Category cat = categories.get(position);
            holder.icon.setText(cat.icon);
            holder.name.setText(cat.name);
            holder.count.setText("Carica...");
            holder.itemView.setOnClickListener(v -> loadCharactersForCategory(cat.id));

            // Load character count
            executor.execute(() -> {
                try {
                    String url = baseUrl + "/characters?category=" + cat.id + "&limit=1&offset=0";
                    String json = httpGetWithAuthRefresh(url);
                    if (json != null) {
                        JSONArray arr = new JSONArray(json);
                        int total = arr.length();
                        mainHandler.post(() -> {
                            if (holder.getAdapterPosition() != RecyclerView.NO_POSITION) {
                                holder.count.setText(total + " personaggi");
                            }
                        });
                    }
                } catch (Exception ignored) {}
            });
        }

        @Override
        public int getItemCount() {
            return categories.size();
        }

        class VH extends RecyclerView.ViewHolder {
            TextView icon, name, count;
            VH(View v) {
                super(v);
                icon = v.findViewById(R.id.category_icon);
                name = v.findViewById(R.id.category_name);
                count = v.findViewById(R.id.category_count);
            }
        }
    }

    // ─── Character List Adapter ────────────────────────────────────

    class CharacterListAdapter extends RecyclerView.Adapter<CharacterListAdapter.VH> {

        @NonNull
        @Override
        public VH onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
            View v = LayoutInflater.from(parent.getContext()).inflate(R.layout.item_character_list, parent, false);
            return new VH(v);
        }

        @Override
        public void onBindViewHolder(@NonNull VH holder, int position) {
            HomeFragment.CharacterItem item = currentCategoryCharacters.get(position);
            holder.emoji.setText(item.emoji);
            holder.name.setText(item.name);
            holder.description.setText(item.description);
            holder.conversations.setText(item.getConversationsString() + " conversazioni");
            holder.itemView.setOnClickListener(v -> {
                if (getActivity() instanceof MainActivity) {
                    ((MainActivity) getActivity()).openChat(item.id, item.name, null, item.avatarImage, item.emoji);
                }
            });
        }

        @Override
        public int getItemCount() {
            return currentCategoryCharacters.size();
        }

        class VH extends RecyclerView.ViewHolder {
            TextView emoji, name, description, conversations;
            VH(View v) {
                super(v);
                emoji = v.findViewById(R.id.char_emoji);
                name = v.findViewById(R.id.char_name);
                description = v.findViewById(R.id.char_description);
                conversations = v.findViewById(R.id.char_conversations);
            }
        }
    }
}
