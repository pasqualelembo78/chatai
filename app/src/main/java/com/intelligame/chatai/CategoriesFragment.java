package com.intelligame.chatai;

import android.content.Intent;
import android.graphics.Paint;
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
import androidx.appcompat.app.AlertDialog;
import androidx.fragment.app.Fragment;
import com.google.android.material.snackbar.Snackbar;
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
    private final ExecutorService executor = new SafeExecutor();
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    private List<CatItem> categories = new ArrayList<>();
    private CategoryGridAdapter gridAdapter;
    private boolean matureEnabled = false;

    private boolean showingCharacters = false;
    private List<HomeFragment.CharacterItem> currentCategoryCharacters = new ArrayList<>();
    private CharacterListAdapter listAdapter;

    // Model for categories with count and locked status
    static class CatItem {
        String id, name, icon;
        boolean locked, premium, adult;
        int mvcCost, characterCount;

        CatItem(String id, String name, String icon, boolean locked, boolean premium, int mvcCost, int characterCount, boolean adult) {
            this.id = id;
            this.name = name;
            this.icon = icon;
            this.locked = locked;
            this.premium = premium;
            this.mvcCost = mvcCost;
            this.characterCount = characterCount;
            this.adult = adult;
        }

        CatItem(String id, String name, String icon, boolean locked, boolean premium, int mvcCost, int characterCount) {
            this(id, name, icon, locked, premium, mvcCost, characterCount, false);
        }
    }

    private static final String OPTIN_ID = "__mature_optin__";

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

        matureEnabled = ((ChatApplication) requireActivity().getApplication()).getPrefs().getShowAdult();

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
                    List<CatItem> list = new ArrayList<>();
                    for (int i = 0; i < arr.length(); i++) {
                        JSONObject obj = arr.getJSONObject(i);
                        String id = obj.optString("id");
                        if ("per_te".equals(id)) continue;
                        boolean adult = obj.optBoolean("adult", false);
                        if (adult && !matureEnabled) continue;
                        list.add(new CatItem(
                            id,
                            obj.optString("name"),
                            obj.optString("icon", "\uD83D\uDCCC"),
                            obj.optBoolean("locked", false),
                            obj.optBoolean("premium", false),
                            obj.optInt("mvc_cost", 0),
                            obj.optInt("character_count", 0),
                            adult
                        ));
                    }
                    addMatureOptInIfNeeded(list);
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
        categories.add(new CatItem("romantici", "Romantici", "\uD83D\uDC95", false, false, 0, 0));
        categories.add(new CatItem("amicizia", "Amicizia", "\uD83E\uDD1D", false, false, 0, 0));
        categories.add(new CatItem("fantasy", "Fantasy", "\uD83E\uDDD9", false, false, 0, 0));
        categories.add(new CatItem("horror", "Horror", "\uD83D\uDC7B", true, false, 200, 0));
        categories.add(new CatItem("anime", "Anime", "\uD83C\uDFB5", false, false, 0, 0));
        categories.add(new CatItem("gamer", "Gamer", "\uD83C\uDFAE", false, false, 0, 0));
        categories.add(new CatItem("detective", "Detective", "\uD83D\uDD75\uFE0F", false, false, 0, 0));
        if (matureEnabled) categories.add(new CatItem("flirt", "Flirt", "\uD83D\uDE08", true, false, 300, 0, true));
        if (matureEnabled) categories.add(new CatItem("seduzione", "Seduzione", "\uD83D\uDE08", true, false, 500, 0, true));
        categories.add(new CatItem("sport", "Sport", "\u26BD", false, false, 0, 0));
        categories.add(new CatItem("cucina", "Cucina", "\uD83C\uDF73", false, false, 0, 0));
        categories.add(new CatItem("medicina", "Medicina", "\uD83C\uDFE5", false, false, 0, 0));
        categories.add(new CatItem("tecnologia", "Tecnologia", "\uD83D\uDCBB", false, false, 0, 0));
        categories.add(new CatItem("creativi", "Creativi", "\uD83C\uDFA8", false, false, 0, 0));
        if (matureEnabled) categories.add(new CatItem("relazioni", "Relazioni", "\uD83D\uDC91", true, false, 300, 0, true));
        categories.add(new CatItem("motivazione", "Motivazione", "\uD83D\uDCAA", false, false, 0, 0));
        categories.add(new CatItem("scuola", "Scuola", "\uD83C\uDF93", false, false, 0, 0));
        categories.add(new CatItem("viaggi", "Viaggi", "\uD83D\uDEE2\uFE0F", false, false, 0, 0));
        categories.add(new CatItem("sopravvivenza", "Sopravvivenza", "\uD83C\uDFD4\uFE0F", false, false, 0, 0));
        categories.add(new CatItem("business", "Business", "\uD83D\uDCBC", false, false, 0, 0));
        categories.add(new CatItem("storia", "Storia", "\uD83C\uDFDB\uFE0F", false, false, 0, 0));
        categories.add(new CatItem("supereroi", "Supereroi", "\uD83D\uDEE1\uFE0F", false, false, 0, 0));
        categories.add(new CatItem("sci_fi", "Fantascienza", "\uD83D\uDE80", false, false, 0, 0));
        if (matureEnabled) categories.add(new CatItem("confessioni", "Confessioni", "\uD83D\uDE48", true, false, 300, 0, true));
        categories.add(new CatItem("premium", "Premium", "\uD83D\uDC8E", false, true, 0, 0));
        addMatureOptInIfNeeded(categories);
        gridAdapter.notifyDataSetChanged();
    }

    private void addMatureOptInIfNeeded(List<CatItem> list) {
        if (matureEnabled) return;
        list.add(new CatItem(OPTIN_ID, "Mostra contenuti maturi", "\uD83D\uDD1E", false, false, 0, 0, false));
    }

    private void showMatureOptIn() {
        AdultConfirmDialog dlg = new AdultConfirmDialog(() -> {
            matureEnabled = true;
            ((ChatApplication) requireActivity().getApplication()).getPrefs().setShowAdult(true);
            loadCategories();
        });
        dlg.show(getParentFragmentManager(), "mature_optin");
    }

    private void loadCharactersForCategory(String categoryId, boolean locked) {
        CatItem selected = null;
        for (CatItem c : categories) {
            if (c.id.equals(categoryId)) { selected = c; break; }
        }
        if (locked) {
            if (selected != null) showUnlockDialog(selected);
            return;
        }
        showingCharacters = true;
        titleText.setText(selected != null ? selected.icon + " " + selected.name : "Personaggi");
        backButton.setText("\u2190");

        currentCategoryCharacters.clear();
        listAdapter.notifyDataSetChanged();
        categoriesRecycler.setLayoutManager(new LinearLayoutManager(requireContext()));
        categoriesRecycler.setAdapter(listAdapter);
        loadingProgress.setVisibility(View.VISIBLE);

        executor.execute(() -> {
            try {
                String url = baseUrl + "/characters?category=" + categoryId + "&limit=200&offset=0";
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
        backButton.setText("\u2190");
        categoriesRecycler.setLayoutManager(new GridLayoutManager(requireContext(), 2));
        categoriesRecycler.setAdapter(gridAdapter);
    }

    private void showUnlockDialog(CatItem cat) {
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

    private void unlockCategory(CatItem cat) {
        executor.execute(() -> {
            try {
                JSONObject body = new JSONObject();
                body.put("content_type", "category");
                body.put("content_id", cat.id);
                body.put("amount", cat.mvcCost);
                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(baseUrl + "/user/mevacoins/spend", "POST", body.toString(), 10000);
                if (resp.statusCode == 200) {
                    JSONObject obj = new JSONObject(resp.body);
                    if (obj.optBoolean("unlocked", false)) {
                        cat.locked = false;
                        mainHandler.post(() -> {
                            gridAdapter.notifyDataSetChanged();
                            showSnackbar("Categoria sbloccata!");
                            loadCharactersForCategory(cat.id, false);
                        });
                        return;
                    }
                }
                mainHandler.post(() -> showSnackbar("MVC insufficienti o errore"));
            } catch (Exception e) {
                mainHandler.post(() -> showSnackbar("Errore: " + e.getMessage()));
            }
        });
    }

    private void showSnackbar(String msg) {
        View root = getView();
        if (root != null) {
            Snackbar.make(root, msg, Snackbar.LENGTH_SHORT).show();
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
            CatItem cat = categories.get(position);
            holder.icon.setText(cat.icon);
            holder.name.setText(cat.name);

            if (OPTIN_ID.equals(cat.id)) {
                holder.name.setPaintFlags(holder.name.getPaintFlags() & ~Paint.STRIKE_THRU_TEXT_FLAG);
                holder.count.setText("Sblocca contenuti per adulti");
                holder.count.setTextColor(0xFF7C4DFF); // primary
                holder.itemView.setAlpha(1.0f);
                return;
            }

            if (cat.characterCount > 0) {
                holder.count.setText(cat.characterCount + " personaggi");
            } else {
                holder.count.setText("Carica...");
            }

            if (cat.locked) {
                holder.name.setPaintFlags(holder.name.getPaintFlags() | Paint.STRIKE_THRU_TEXT_FLAG);
                holder.count.setText("\uD83D\uDD12 " + cat.mvcCost + " MVC per sbloccare");
                holder.count.setTextColor(0xFFFF9800); // orange
                holder.itemView.setAlpha(0.7f);
            } else {
                holder.name.setPaintFlags(holder.name.getPaintFlags() & ~Paint.STRIKE_THRU_TEXT_FLAG);
                holder.count.setTextColor(0xFF6B6B80); // on_surface_dim
                holder.itemView.setAlpha(1.0f);
            }

            holder.itemView.setOnClickListener(v -> {
                if (OPTIN_ID.equals(cat.id)) {
                    showMatureOptIn();
                    return;
                }
                loadCharactersForCategory(cat.id, cat.locked);
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
