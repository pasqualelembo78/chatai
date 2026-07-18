package com.intelligame.chatai;

import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.appcompat.app.AlertDialog;
import androidx.fragment.app.Fragment;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.google.android.material.button.MaterialButton;
import androidx.appcompat.widget.SwitchCompat;
import com.google.android.material.snackbar.Snackbar;
import com.google.android.material.textfield.TextInputEditText;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;


import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class ProfileFragment extends Fragment {

    private TextInputEditText fieldNickname, fieldServerUrl;
    private MaterialButton btnSaveNickname, btnSaveServer, btnResetAll, btnImportManage;
    private TextView nicknameStatus, serverStatus, resetStatus;
    private TextView mevacoinsBalance;
    private SwitchCompat switchAdultContent;
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
        Button btnRicarica = view.findViewById(R.id.btn_ricarica);
        Button btnGuadagna = view.findViewById(R.id.btn_guadagna);
        Button btnEditPrefs = view.findViewById(R.id.btn_edit_preferences);
        switchAdultContent = view.findViewById(R.id.switch_adult_content);
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

        // Adult content switch
        switchAdultContent.setChecked(prefs.getShowAdult());
        switchAdultContent.setOnCheckedChangeListener((buttonView, isChecked) -> {
            prefs.setShowAdult(isChecked);
            saveAdultPreference(isChecked);
            Snackbar.make(requireView(),
                isChecked ? "Contenuti adulti attivati" : "Contenuti adulti disattivati",
                Snackbar.LENGTH_SHORT).show();
        });

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
        loadReferralCode();

        preferitiRecycler = view.findViewById(R.id.prof_preferiti_recycler);
        preferitiTitle = view.findViewById(R.id.prof_preferiti_title);
        pertRecycler = view.findViewById(R.id.prof_perte_recycler);
        pertTitle = view.findViewById(R.id.prof_perte_title);

        preferitiRecycler.setLayoutManager(new LinearLayoutManager(getContext(), LinearLayoutManager.HORIZONTAL, false));
        pertRecycler.setLayoutManager(new LinearLayoutManager(getContext(), LinearLayoutManager.HORIZONTAL, false));

        boolean ageVerified = prefs.getAdultBirthYear() > 0;
        preferitiAdapter = new CharacterCardAdapter(preferitiChars, character -> {
            if (character.isAdult && !ageVerified) {
                AdultConfirmDialog dialog = new AdultConfirmDialog(() -> openCharacterDetail(character));
                dialog.show(getParentFragmentManager(), "adult_confirm");
            } else {
                openCharacterDetail(character);
            }
        }, (character, isFavorite) -> toggleFavorite(character, isFavorite));
        preferitiRecycler.setAdapter(preferitiAdapter);

        pertAdapter = new CharacterCardAdapter(pertChars, character -> {
            if (character.isAdult && !ageVerified) {
                AdultConfirmDialog dialog = new AdultConfirmDialog(() -> openCharacterDetail(character));
                dialog.show(getParentFragmentManager(), "adult_confirm");
            } else {
                openCharacterDetail(character);
            }
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
                        }
                    });
                }
            } catch (Exception ignored) {}
        });
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

    private void saveAdultPreference(boolean showAdult) {
        executor.execute(() -> {
            try {
                JSONObject body = new JSONObject();
                body.put("show_adult", showAdult);
                mAuth.requestWithRefresh(baseUrl + "/user/preferences", "PUT", body.toString(), 5000);
            } catch (Exception ignored) {}
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
}
