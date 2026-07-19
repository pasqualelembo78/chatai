package com.intelligame.chatai;

import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.graphics.Typeface;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.appcompat.app.AlertDialog;
import androidx.core.content.ContextCompat;
import androidx.fragment.app.Fragment;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.google.android.material.button.MaterialButton;
import com.google.android.material.chip.Chip;
import androidx.appcompat.widget.SwitchCompat;
import com.google.android.material.snackbar.Snackbar;
import com.google.android.material.textfield.TextInputEditText;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class ProfileFragment extends Fragment {

    private TextInputEditText fieldNickname, fieldServerUrl;
    private MaterialButton btnSaveNickname, btnSaveServer, btnResetAll, btnImportManage;
    private TextView nicknameStatus, serverStatus, resetStatus;
    private TextView mevacoinsBalance;
    private TextView mvcLevelText;
    private TextView mvcLevelProgressText;
    private ProgressBar mvcLevelProgress;
    private com.google.android.material.chip.ChipGroup mvcBadgesGroup;
    private TextView mvcBadgesEmpty;
    private View adminDivider;
    private android.widget.LinearLayout adminSection;

    private TextView referralCodeText;
    private MaterialButton btnCopyReferral, btnShareReferral, btnSocialShare;
    private MaterialButton btnDeleteAccount;
    private TextView shareStatusText;
    private TextView deleteAccountStatus;

    private String baseUrl;
    private String userId;
    private PrefsManager prefs;
    private ChatApplication app;
    private AuthManager mAuth;

    private RecyclerView preferitiRecycler;
    private TextView preferitiTitle;
    private CharacterCardAdapter preferitiAdapter;
    private final java.util.List<HomeFragment.CharacterItem> preferitiChars = new java.util.ArrayList<>();

    private RecyclerView pertRecycler;
    private TextView pertTitle;
    private CharacterCardAdapter pertAdapter;
    private final java.util.List<HomeFragment.CharacterItem> pertChars = new java.util.ArrayList<>();

    private ExecutorService executor = new SafeExecutor();
    private Handler mainHandler = new Handler(Looper.getMainLooper());

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater, @Nullable ViewGroup container, @Nullable Bundle savedInstanceState) {
        View view = inflater.inflate(R.layout.fragment_profile, container, false);

        app = (ChatApplication) requireActivity().getApplication();
        mAuth = app.getAuthManager();
        prefs = app.getPrefs();
        baseUrl = prefs.getServerUrl().replace("/chat", "");
        userId = prefs.getUsername();

        fieldNickname = view.findViewById(R.id.field_nickname);
        fieldServerUrl = view.findViewById(R.id.field_server_url);
        btnSaveNickname = view.findViewById(R.id.btn_save_nickname);
        btnSaveServer = view.findViewById(R.id.btn_save_server);
        btnResetAll = view.findViewById(R.id.btn_reset_all);
        nicknameStatus = view.findViewById(R.id.nickname_status);
        serverStatus = view.findViewById(R.id.server_status);
        resetStatus = view.findViewById(R.id.reset_status);

        mevacoinsBalance = view.findViewById(R.id.mevacoins_balance_text);
        mvcLevelText = view.findViewById(R.id.mvc_level_text);
        mvcLevelProgressText = view.findViewById(R.id.mvc_level_progress_text);
        mvcLevelProgress = view.findViewById(R.id.mvc_level_progress);
        mvcBadgesGroup = view.findViewById(R.id.mvc_badges_group);
        mvcBadgesEmpty = view.findViewById(R.id.mvc_badges_empty);
        Button btnRicarica = view.findViewById(R.id.btn_ricarica);
        Button btnGuadagna = view.findViewById(R.id.btn_guadagna);
        Button         btnEditPrefs = view.findViewById(R.id.btn_edit_preferences);
        adminDivider = view.findViewById(R.id.admin_divider);
        adminSection = view.findViewById(R.id.admin_section);
        btnImportManage = view.findViewById(R.id.btn_import_manage);

        referralCodeText = view.findViewById(R.id.referral_code_text);
        btnCopyReferral = view.findViewById(R.id.btn_copy_referral);
        btnShareReferral = view.findViewById(R.id.btn_share_referral);
        btnSocialShare = view.findViewById(R.id.btn_social_share);
        shareStatusText = view.findViewById(R.id.share_status_text);

        btnDeleteAccount = view.findViewById(R.id.btn_delete_account);
        deleteAccountStatus = view.findViewById(R.id.delete_account_status);

        fieldNickname.setText(prefs.getUsername());
        fieldServerUrl.setText(prefs.getServerUrl());

        btnSaveNickname.setOnClickListener(v -> saveNickname());
        btnSaveServer.setOnClickListener(v -> saveServerUrl());
        btnResetAll.setOnClickListener(v -> confirmReset());

        btnEditPrefs.setOnClickListener(v -> {
            Intent intent = new Intent(requireActivity(), OnboardingActivity.class);
            intent.putExtra("editing", true);
            startActivity(intent);
        });

        btnGuadagna.setOnClickListener(v -> {
            Intent intent = new Intent(requireActivity(), MvcEarnActivity.class);
            startActivity(intent);
        });

        // btnRicarica nascosto — assenza di Play Billing implementato
        btnRicarica.setVisibility(View.GONE);

        btnCopyReferral.setOnClickListener(v -> copyReferralCode());
        btnShareReferral.setOnClickListener(v -> shareReferral());
        btnSocialShare.setOnClickListener(v -> doSocialShare());

        btnDeleteAccount.setOnClickListener(v -> confirmDeleteAccount());

        // Admin section - show only for admin/moderator roles
        String role = mAuth.getRole();
        if ("admin".equals(role) || "moderator".equals(role)) {
            adminDivider.setVisibility(View.VISIBLE);
            adminSection.setVisibility(View.VISIBLE);
            btnImportManage.setOnClickListener(v -> {
                Intent intent = new Intent(requireActivity(), ImportActivity.class);
                startActivity(intent);
            });
        }

        loadMevacoins();
        loadGamification();
        loadMissions();
        loadReferralCode();
        showMvcOnboardingIfNeeded();

        preferitiRecycler = view.findViewById(R.id.prof_preferiti_recycler);
        preferitiTitle = view.findViewById(R.id.prof_preferiti_title);
        pertRecycler = view.findViewById(R.id.prof_perte_recycler);
        pertTitle = view.findViewById(R.id.prof_perte_title);

        preferitiRecycler.setLayoutManager(new LinearLayoutManager(getContext(), LinearLayoutManager.HORIZONTAL, false));
        pertRecycler.setLayoutManager(new LinearLayoutManager(getContext(), LinearLayoutManager.HORIZONTAL, false));

        preferitiAdapter = new CharacterCardAdapter(preferitiChars, character -> {
            openCharacterDetail(character);
        }, (character, isFavorite) -> toggleFavorite(character, isFavorite));
        preferitiRecycler.setAdapter(preferitiAdapter);

        pertAdapter = new CharacterCardAdapter(pertChars, character -> {
            openCharacterDetail(character);
        }, (character, isFavorite) -> toggleFavorite(character, isFavorite));
        pertRecycler.setAdapter(pertAdapter);

        loadPreferiti();
        loadPerTe();

        return view;
    }

    @Override
    public void onStop() {
        super.onStop();
    }

    private void loadMevacoins() {
        executor.execute(() -> {
            try {
                AuthManager.HttpResponse httpResp = mAuth.requestWithRefresh(baseUrl + "/user/mevacoins", "GET", null, 5000);
                if (httpResp.statusCode == 200) {
                    JSONObject obj = new JSONObject(httpResp.body);
                    int balance = obj.optInt("balance", 0);
                    mainHandler.post(() -> {
                        if (mevacoinsBalance != null) {
                            mevacoinsBalance.setText(balance + " MVC");
                            pulseView(mevacoinsBalance);
                        }
                    });
                }
            } catch (Exception ignored) {}
        });
    }

    private void pulseView(View v) {
        if (v == null || !isAdded()) return;
        v.animate().scaleX(1.15f).scaleY(1.15f).setDuration(150)
                .withEndAction(() -> v.animate().scaleX(1f).scaleY(1f).setDuration(150).start())
                .start();
    }

    private void loadGamification() {
        executor.execute(() -> {
            try {
                AuthManager.HttpResponse httpResp =
                        mAuth.requestWithRefresh(baseUrl + "/user/mevacoins/badges", "GET", null, 5000);
                if (httpResp == null || httpResp.statusCode != 200) return;
                JSONObject obj = new JSONObject(httpResp.body);
                JSONObject level = obj.optJSONObject("level");
                final int levelNum = level != null ? level.optInt("level", 1) : 1;
                final int into = level != null ? level.optInt("into_level", 0) : 0;
                final int needed = level != null ? level.optInt("needed", 200) : 200;
                final int progressPct = level != null ? (int) (level.optDouble("progress", 0) * 100) : 0;
                JSONArray badges = obj.optJSONArray("badges");
                mainHandler.post(() -> {
                    if (mvcLevelText != null) mvcLevelText.setText("Livello " + levelNum);
                    if (mvcLevelProgressText != null)
                        mvcLevelProgressText.setText(into + "/" + needed + " MVC");
                    if (mvcLevelProgress != null) mvcLevelProgress.setProgress(progressPct);
                    renderBadges(badges);
                });
            } catch (Exception ignored) {}
        });
    }

    private void renderBadges(JSONArray badges) {
        if (mvcBadgesGroup == null) return;
        mvcBadgesGroup.removeAllViews();
        boolean anyEarned = false;
        if (badges != null) {
            for (int i = 0; i < badges.length(); i++) {
                try {
                    JSONObject b = badges.getJSONObject(i);
                    boolean earned = b.optBoolean("earned", false);
                    if (earned) anyEarned = true;
                    Chip chip = new Chip(requireContext());
                    chip.setText(b.optString("name", ""));
                    chip.setCheckable(false);
                    chip.setClickable(false);
                    int tint = earned ? R.color.primary : android.R.color.darker_gray;
                    chip.setChipBackgroundColorResource(tint);
                    chip.setTextColor(earned ? getResources().getColor(android.R.color.white)
                            : getResources().getColor(R.color.on_surface_variant));
                    mvcBadgesGroup.addView(chip);
                } catch (Exception ignored) {}
            }
        }
        mvcBadgesGroup.setVisibility(anyEarned ? View.VISIBLE : View.GONE);
        if (mvcBadgesEmpty != null)
            mvcBadgesEmpty.setVisibility(anyEarned ? View.GONE : View.VISIBLE);
    }

    private void showMvcOnboardingIfNeeded() {
        boolean onboarded = prefs.isMvcOnboarded();
        if (onboarded) return;
        if (!isAdded() || getActivity() == null) return;
        new AlertDialog.Builder(getActivity())
                .setTitle("Come funzionano i MevaCoin (MVC)")
                .setMessage("Guadagni MVC ogni giorno: fai check-in, mantieni la streak di 30 giorni, "
                        + "completa le missioni, invita amici o condividi l'app.\n\n"
                        + "Poi spendili nel Negozio: sblocca personaggi e funzioni, "
                        + "compra consumabili come Rigenera messaggio, Boost velocita, "
                        + "Pack personalita e Streak Shield. Sali di livello e sblocca badge!")
                .setPositiveButton("Ho capito", (d, w) -> prefs.setMvcOnboarded(true))
                .show();
    }

    private void loadReferralCode() {
        executor.execute(() -> {
            try {
                AuthManager.HttpResponse httpResp = mAuth.requestWithRefresh(baseUrl + "/user/referral/code", "GET", null, 5000);
                if (httpResp.statusCode == 200) {
                    JSONObject obj = new JSONObject(httpResp.body);
                    String code = obj.optString("code", "");
                    mainHandler.post(() -> {
                        if (referralCodeText != null) {
                            referralCodeText.setText(code);
                        }
                    });
                }
            } catch (Exception ignored) {}
        });
    }

    private void copyReferralCode() {
        String code = referralCodeText.getText().toString();
        if (code.isEmpty() || code.equals("...")) return;
        ClipboardManager clipboard = (ClipboardManager) requireContext().getSystemService(Context.CLIPBOARD_SERVICE);
        ClipData clip = ClipData.newPlainText("codice_referral", code);
        clipboard.setPrimaryClip(clip);
        Toast.makeText(getContext(), "Codice copiato: " + code, Toast.LENGTH_SHORT).show();
    }

    private void shareReferral() {
        String code = referralCodeText.getText().toString();
        if (code.isEmpty() || code.equals("...")) return;
        String text = "Unisciti a me su Aria! Inserisci il mio codice referral " + code + " e ricevi 50 MVC gratis. Scarica l'app: " + baseUrl.replace("/chat", "");
        Intent share = new Intent(Intent.ACTION_SEND);
        share.setType("text/plain");
        share.putExtra(Intent.EXTRA_TEXT, text);
        startActivity(Intent.createChooser(share, "Invita amici"));
    }

    private void doSocialShare() {
        String text = "Sto chattando con personaggi incredibili su Aria! 💬 Unisciti anche tu e crea il tuo personaggio AI! 🚀";
        Intent share = new Intent(Intent.ACTION_SEND);
        share.setType("text/plain");
        share.putExtra(Intent.EXTRA_TEXT, text);
        startActivity(Intent.createChooser(share, "Condividi e guadagna 30 MVC"));

        executor.execute(() -> {
            try {
                Thread.sleep(2000);
            } catch (InterruptedException ignored) {}
            reportSocialShare();
        });
    }

    private void reportSocialShare() {
        executor.execute(() -> {
            try {
                JSONObject body = new JSONObject();
                body.put("platform", "android_share");
                AuthManager.HttpResponse httpResp = mAuth.requestWithRefresh(baseUrl + "/user/mevacoins/share", "POST", body.toString(), 5000);

                if (httpResp.statusCode == 200) {
                    JSONObject obj = new JSONObject(httpResp.body);
                    if (obj.optString("status", "").equals("ok")) {
                        int earned = obj.optInt("earned", 30);
                        mainHandler.post(() -> {
                            shareStatusText.setText("+" + earned + " MVC guadagnati!");
                            shareStatusText.setVisibility(View.VISIBLE);
                            loadMevacoins();
                        });
                    } else if (obj.optString("error", "").equals("limite_giornaliero")) {
                        mainHandler.post(() -> {
                            shareStatusText.setText("Hai raggiunto il limite giornaliero (3/3)");
                            shareStatusText.setVisibility(View.VISIBLE);
                        });
                    }
                } else {
                    mainHandler.post(() -> {
                        shareStatusText.setText("Errore: riprova più tardi");
                        shareStatusText.setVisibility(View.VISIBLE);
                    });
                }
            } catch (Exception e) {
                mainHandler.post(() -> {
                    shareStatusText.setText("Errore: " + e.getMessage());
                    shareStatusText.setVisibility(View.VISIBLE);
                });
            }
        });
    }

    private void saveNickname() {
        String nick = fieldNickname.getText().toString().trim();
        if (nick.isEmpty()) {
            nicknameStatus.setText("Il nickname non può essere vuoto");
            nicknameStatus.setTextColor(getResources().getColor(R.color.error));
            nicknameStatus.setVisibility(View.VISIBLE);
            return;
        }
        prefs.setUsername(nick);
        userId = nick;
        nicknameStatus.setText("Nickname salvato! Riconnettiti per applicare le modifiche.");
        nicknameStatus.setTextColor(getResources().getColor(R.color.status_connected));
        nicknameStatus.setVisibility(View.VISIBLE);
        Snackbar.make(requireView(), "Nickname: " + nick, Snackbar.LENGTH_SHORT).show();
    }

    private void saveServerUrl() {
        String url = fieldServerUrl.getText().toString().trim();
        if (url.isEmpty()) {
            serverStatus.setText("URL non valido");
            serverStatus.setTextColor(getResources().getColor(R.color.error));
            serverStatus.setVisibility(View.VISIBLE);
            return;
        }
        prefs.setServerUrl(url);
        baseUrl = url.replace("/chat", "");
        serverStatus.setText("URL server salvato! Riconnettiti per applicare.");
        serverStatus.setTextColor(getResources().getColor(R.color.status_connected));
        serverStatus.setVisibility(View.VISIBLE);
        Snackbar.make(requireView(), "Server: " + url, Snackbar.LENGTH_SHORT).show();
    }

    private void confirmDeleteAccount() {
        new AlertDialog.Builder(requireContext())
            .setTitle("Elimina account")
            .setMessage("L'account e tutti i dati associati (personaggi, conversazioni, cronologia) verranno cancellati in modo permanente e irreversibile.\n\nVuoi procedere?")
            .setPositiveButton("Elimina", (dialog, which) -> deleteAccount())
            .setNegativeButton("Annulla", null)
            .show();
    }

    private void deleteAccount() {
        btnDeleteAccount.setEnabled(false);
        deleteAccountStatus.setText("Eliminazione in corso...");
        deleteAccountStatus.setVisibility(View.VISIBLE);

        executor.execute(() -> {
            try {
                AuthManager.HttpResponse httpResp = mAuth.requestWithRefresh(
                    baseUrl + "/user/delete", "POST", "{}", 10000);
                boolean serverOk = httpResp.statusCode >= 200 && httpResp.statusCode < 300;

                try {
                    app.getLocalDb().resetAll();
                } catch (Exception ignored) {}

                prefs.clearAll();

                mainHandler.post(() -> {
                    if (!isAdded()) return;
                    if (serverOk) {
                        Toast.makeText(getContext(), "Account eliminato", Toast.LENGTH_LONG).show();
                    } else {
                        Toast.makeText(getContext(), "Account eliminato (locale)", Toast.LENGTH_LONG).show();
                    }
                    Intent intent = new Intent(requireActivity(), LoginActivity.class);
                    intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
                    startActivity(intent);
                    requireActivity().finish();
                });
            } catch (Exception e) {
                mainHandler.post(() -> {
                    if (!isAdded()) return;
                    btnDeleteAccount.setEnabled(true);
                    deleteAccountStatus.setText("\u274c Errore: " + e.getMessage());
                });
            }
        });
    }

    private void confirmReset() {
        new AlertDialog.Builder(requireContext())
            .setTitle("Resetta tutti i dati")
            .setMessage("Tutta la cronologia chat, la memoria AI e le relazioni verranno cancellate. I personaggi non si ricorderanno più di te.\n\nQuesta operazione è irreversibile.")
            .setPositiveButton("Resetta", (dialog, which) -> resetAllData())
            .setNegativeButton("Annulla", null)
            .show();
    }

    private void resetAllData() {
        btnResetAll.setEnabled(false);
        resetStatus.setText("Resettando...");
        resetStatus.setVisibility(View.VISIBLE);

        executor.execute(() -> {
            try {
                app.getLocalDb().resetAll();

                try {
                    AuthManager.HttpResponse httpResp = mAuth.requestWithRefresh(baseUrl + "/user/reset", "POST", null, 10000);
                } catch (Exception ignored) {}

                mainHandler.post(() -> {
                    if (!isAdded()) return;
                    resetStatus.setText("\u2705 Dati resettati con successo");
                    btnResetAll.setEnabled(true);
                    Snackbar.make(requireView(), "Memoria AI cancellata", Snackbar.LENGTH_LONG).show();
                });
            } catch (Exception e) {
                mainHandler.post(() -> {
                    if (!isAdded()) return;
                    resetStatus.setText("\u274c Errore: " + e.getMessage());
                    btnResetAll.setEnabled(true);
                });
            }
        });
    }

    private void openCharacterDetail(HomeFragment.CharacterItem character) {
        Intent intent = new Intent(getActivity(), CharacterDetailActivity.class);
        intent.putExtra("character_id", character.id);
        startActivity(intent);
    }

    private void toggleFavorite(HomeFragment.CharacterItem character, boolean isFavorite) {
        executor.execute(() -> {
            try {
                if (isFavorite) {
                    app.getLocalDb().addFavorite(character.id);
                } else {
                    app.getLocalDb().removeFavorite(character.id);
                }
                mainHandler.post(this::loadPreferiti);
            } catch (Exception ignored) {}
        });
    }

    private String httpGetWithAuth(String urlString) {
        try {
            AuthManager.HttpResponse httpResp = mAuth.requestWithRefresh(urlString, "GET", null, 8000);
            if (httpResp.statusCode == 200) {
                return httpResp.body;
            }
        } catch (Exception e) {
            return null;
        }
        return null;
    }

    private void loadPreferiti() {
        executor.execute(() -> {
            try {
                java.util.List<String> favIds = app.getLocalDb().getAllFavoriteIds();
                if (favIds.isEmpty()) {
                    mainHandler.post(this::hidePreferiti);
                    return;
                }
                String chatBase = prefs.getServerUrl();
                String json = httpGetWithAuth(chatBase + "/characters?category=all&limit=500");
                if (json == null) {
                    mainHandler.post(this::hidePreferiti);
                    return;
                }
                JSONArray arr = new JSONArray(json);
                java.util.List<HomeFragment.CharacterItem> list = new java.util.ArrayList<>();
                java.util.Set<String> favIdSet = new java.util.HashSet<>(favIds);
                for (int i = 0; i < arr.length(); i++) {
                    HomeFragment.CharacterItem item = HomeFragment.CharacterItem.fromJson(arr.getJSONObject(i));
                    if (favIdSet.contains(item.id)) {
                        list.add(item);
                    }
                }
                mainHandler.post(() -> {
                    if (list.isEmpty()) {
                        hidePreferiti();
                    } else {
                        preferitiChars.clear();
                        preferitiChars.addAll(list);
                        preferitiAdapter.setFavoriteIds(favIdSet);
                        preferitiAdapter.notifyDataSetChanged();
                        preferitiRecycler.setVisibility(View.VISIBLE);
                        preferitiTitle.setVisibility(View.VISIBLE);
                    }
                });
            } catch (Exception e) {
                mainHandler.post(this::hidePreferiti);
            }
        });
    }

    private void hidePreferiti() {
        preferitiRecycler.setVisibility(View.GONE);
        preferitiTitle.setVisibility(View.GONE);
    }

    private void loadPerTe() {
        executor.execute(() -> {
            try {
                String chatBase = prefs.getServerUrl();
                String json = httpGetWithAuth(chatBase + "/characters?category=per_te&limit=500");
                if (json == null) {
                    mainHandler.post(this::hidePerTe);
                    return;
                }
                JSONArray arr = new JSONArray(json);
                java.util.List<HomeFragment.CharacterItem> list = new java.util.ArrayList<>();
                for (int i = 0; i < arr.length(); i++) {
                    list.add(HomeFragment.CharacterItem.fromJson(arr.getJSONObject(i)));
                }
                mainHandler.post(() -> {
                    if (list.isEmpty()) {
                        hidePerTe();
                    } else {
                        pertChars.clear();
                        pertChars.addAll(list);
                        pertAdapter.notifyDataSetChanged();
                        pertRecycler.setVisibility(View.VISIBLE);
                        pertTitle.setVisibility(View.VISIBLE);
                    }
                });
            } catch (Exception e) {
                mainHandler.post(this::hidePerTe);
            }
        });
    }

    private void hidePerTe() {
        pertRecycler.setVisibility(View.GONE);
        pertTitle.setVisibility(View.GONE);
    }

    private void loadMissions() {
        executor.execute(() -> {
            try {
                String url = prefs.getServerUrl() + "/user/mevacoins/missions";
                String resp = httpGetWithAuth(url);
                if (resp == null) return;
                JSONObject obj = new JSONObject(resp);
                JSONArray missions = obj.optJSONArray("missions");
                if (missions == null) return;
                List<MissionItem> items = new ArrayList<>();
                int completed = 0;
                int totalReward = 0;
                for (int i = 0; i < missions.length(); i++) {
                    JSONObject m = missions.getJSONObject(i);
                    String code = m.optString("code");
                    String title = m.optString("title");
                    String desc = m.optString("description");
                    int progress = m.optInt("progress");
                    int target = m.optInt("target");
                    int reward = m.optInt("reward");
                    boolean awarded = m.optBoolean("awarded");
                    if (awarded) completed++;
                    totalReward += reward;
                    items.add(new MissionItem(code, title, desc, progress, target, reward, awarded));
                }
                int finalCompleted = completed;
                int finalTotal = totalReward;
                mainHandler.post(() -> {
                    LinearLayout container = requireView().findViewById(R.id.mission_container);
                    TextView summary = requireView().findViewById(R.id.mission_summary);
                    if (container.getChildCount() > 2) {
                        container.removeViews(2, container.getChildCount() - 2);
                    }
                    summary.setText(String.format(Locale.getDefault(),
                            "Completate %d/%d  •  fino a %d MVC",
                            finalCompleted, items.size(), finalTotal));
                    for (MissionItem it : items) {
                        container.addView(buildMissionRow(it));
                    }
                });
            } catch (Exception e) {
                e.printStackTrace();
            }
        });
    }

    private View buildMissionRow(MissionItem it) {
        Context ctx = requireContext();
        LinearLayout wrapper = new LinearLayout(ctx);
        wrapper.setOrientation(LinearLayout.VERTICAL);
        wrapper.setLayoutParams(new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        wrapper.setPadding(0, 8, 0, 8);

        View divider = new View(ctx);
        divider.setLayoutParams(new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 1));
        divider.setBackgroundColor(ContextCompat.getColor(ctx, R.color.outline));
        wrapper.addView(divider);

        LinearLayout row = new LinearLayout(ctx);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setLayoutParams(new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        row.setPadding(0, 8, 0, 0);

        LinearLayout left = new LinearLayout(ctx);
        left.setOrientation(LinearLayout.VERTICAL);
        left.setLayoutParams(new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

        TextView tTitle = new TextView(ctx);
        tTitle.setText(it.title);
        tTitle.setTextSize(14);
        tTitle.setTypeface(null, Typeface.BOLD);
        tTitle.setTextColor(ContextCompat.getColor(ctx,
                it.awarded ? R.color.status_connected : R.color.on_surface));
        left.addView(tTitle);

        TextView tDesc = new TextView(ctx);
        tDesc.setText(it.description);
        tDesc.setTextSize(11);
        tDesc.setTextColor(ContextCompat.getColor(ctx, R.color.on_surface_variant));
        left.addView(tDesc);

        LinearLayout right = new LinearLayout(ctx);
        right.setOrientation(LinearLayout.VERTICAL);
        right.setGravity(Gravity.END | Gravity.CENTER_VERTICAL);
        right.setLayoutParams(new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        TextView tProg = new TextView(ctx);
        int shown = Math.min(it.progress, it.target);
        tProg.setText(shown + "/" + it.target);
        tProg.setTextSize(13);
        tProg.setTypeface(null, Typeface.BOLD);
        tProg.setTextColor(ContextCompat.getColor(ctx, R.color.on_surface));
        right.addView(tProg);

        TextView tRew = new TextView(ctx);
        tRew.setText((it.awarded ? "\u2713 +" : "+") + it.reward + " MVC");
        tRew.setTextSize(11);
        tRew.setTextColor(ContextCompat.getColor(ctx,
                it.awarded ? R.color.status_connected : R.color.primary));
        right.addView(tRew);

        row.addView(left);
        row.addView(right);
        wrapper.addView(row);
        return wrapper;
    }

    private static class MissionItem {
        final String code;
        final String title;
        final String description;
        final int progress;
        final int target;
        final int reward;
        final boolean awarded;

        MissionItem(String code, String title, String description,
                   int progress, int target, int reward, boolean awarded) {
            this.code = code;
            this.title = title;
            this.description = description;
            this.progress = progress;
            this.target = target;
            this.reward = reward;
            this.awarded = awarded;
        }
    }
}
