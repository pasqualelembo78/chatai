package com.intelligame.chatai;

import android.Manifest;
import android.app.AlertDialog;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.media.MediaRecorder;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.MediaStore;
import android.util.Base64;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.fragment.app.Fragment;
import androidx.fragment.app.FragmentManager;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;
import android.text.Editable;
import android.text.TextUtils;
import android.text.TextWatcher;
import android.util.Log;
import android.view.KeyEvent;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.view.inputmethod.EditorInfo;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.ImageButton;
import android.widget.ImageView;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.File;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Locale;
import java.util.Map;

import io.socket.client.Socket;
import io.socket.emitter.Emitter;


public class MainFragment extends Fragment {

    private static final String TAG = "MainFragment";
    private static final int TYPING_TIMER_LENGTH = 600;
    private static final int CONNECTION_TIMEOUT_MS = 15000;

    private RecyclerView mMessagesView;
    private EditText mInputMessageView;
    private TextView mEmptyChat;
    private TextView mCharacterNameTv;
    private TextView mConnectionStatus;
    private ImageButton mSettingsButton;
    private ImageButton mHelpButton;
    private ImageButton mCopyButton;
    private ImageButton mExtraOptionsButton;
    private ImageView mChatBackground;
    private ImageView mHeaderAvatar;
    private TextView mHeaderAvatarEmoji;
    private List<Message> mMessages = new ArrayList<Message>();
    private JSONObject mSessionMemory = new JSONObject();
    private RecyclerView.Adapter mAdapter;
    private boolean mTyping = false;
    private Handler mTypingHandler = new Handler(Looper.getMainLooper());
    private String mUsername;
    private String mUserId;
    private String mCharacterId;
    private String mCharacterName;
    private String mCharacterImageUrl;
    private String mCharacterAvatarImage;
    private String mCharacterEmoji;
    private Socket mSocket;
    private PrefsManager mPrefs;
    private AuthManager mAuth;
    private LocalDatabaseHelper mLocalDb;
    private FrameLayout mBannerAdContainer;
    private AdManager mAdManager;
    private ImageButton mMicButton;
    private ImageButton mImageAttachButton;
    private ImageView mImagePreview;
    private String mPendingImageBase64;
    private String mPendingImageMime;
    private static final int REQUEST_PICK_IMAGE = 200;
    private MediaRecorder mRecorder;
    private String mAudioFilePath;
    private boolean mIsRecording = false;

    private boolean mSocketConnected = false;
    private boolean mRegistered = false;
    private boolean mApiOnline = false;
    private boolean mMemoryLoaded = false;
    private String mLastError = null;
    private long mConnectStartTime = 0;
    private long mPingStartTime = 0;
    private String mLatencyText = "--";

    private String mConnStage = "";
    private Handler mConnTimeoutHandler = new Handler(Looper.getMainLooper());
    private Message mStreamingMessage;
    private int mStreamingPosition = -1;
    private boolean mStreaming = false;

    public MainFragment() {
        super();
    }

    private void safeRunOnUiThread(Runnable action) {
        if (getActivity() == null || !isAdded()) return;
        getActivity().runOnUiThread(action);
    }

    @Override
    public void onAttach(Context context) {
        super.onAttach(context);
        mAdapter = new MessageAdapter(context, mMessages);
    }

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setHasOptionsMenu(true);

        if (getActivity() == null) return;
        ChatApplication app = (ChatApplication) getActivity().getApplication();
        mSocket = app.getSocket();
        mPrefs = app.getPrefs();
        mAuth = app.getAuthManager();
        mLocalDb = app.getLocalDb();
        mSocket.on(Socket.EVENT_CONNECT, onConnect);
        mSocket.on(Socket.EVENT_DISCONNECT, onDisconnect);
        mSocket.on(Socket.EVENT_CONNECT_ERROR, onConnectError);
        mSocket.on("new message", onNewMessage);
        mSocket.on("stream start", onStreamStart);
        mSocket.on("stream token", onStreamToken);
        mSocket.on("stream complete", onStreamComplete);
        mSocket.on("stream error", onStreamError);
        mSocket.on("typing", onTyping);
        mSocket.on("stop typing", onStopTyping);
        mSocket.on("login", onAutoLogin);
        mSocket.on("pong", onPong);
        mSocket.connect();
    }

    @Override
    public View onCreateView(LayoutInflater inflater, ViewGroup container,
                             Bundle savedInstanceState) {
        return inflater.inflate(R.layout.fragment_main, container, false);
    }

    @Override
    public void onResume() {
        super.onResume();
        if (getActivity() == null) return;
        ChatApplication app = (ChatApplication) getActivity().getApplication();

        Socket freshSocket = app.getSocket();
        if (freshSocket != mSocket) {
            mSocket.off(Socket.EVENT_CONNECT, onConnect);
            mSocket.off(Socket.EVENT_DISCONNECT, onDisconnect);
            mSocket.off(Socket.EVENT_CONNECT_ERROR, onConnectError);
            mSocket.off("new message", onNewMessage);
            mSocket.off("stream start", onStreamStart);
            mSocket.off("stream token", onStreamToken);
            mSocket.off("stream complete", onStreamComplete);
            mSocket.off("stream error", onStreamError);
            mSocket.off("typing", onTyping);
            mSocket.off("stop typing", onStopTyping);
            mSocket.off("login", onAutoLogin);
            mSocket.off("pong", onPong);
            mSocket = freshSocket;
            reattachSocketListeners();
        }

        if (!mSocket.connected()) {
            mSocketConnected = false;
            mRegistered = false;
            setConnStage("handshake");
            startConnTimeout();
            mSocket.connect();
        } else if (!mRegistered) {
            mSocketConnected = true;
            setConnStage("verify_api");
            JSONObject data = new JSONObject();
            try {
                data.put("username", mUsername);
                data.put("character", mCharacterId);
                data.put("user_id", mUserId);
                mSocket.emit("add user", data);
            } catch (JSONException e) {}
        }
        updateConnectionStatus();
    }

    @Override
    public void onDestroy() {
        super.onDestroy();
        // Clean up banner ad
        if (mAdManager != null) {
            mAdManager.destroyBanner();
        }
        mSocket.off(Socket.EVENT_CONNECT, onConnect);
        mSocket.off(Socket.EVENT_DISCONNECT, onDisconnect);
        mSocket.off(Socket.EVENT_CONNECT_ERROR, onConnectError);
        mSocket.off("new message", onNewMessage);
        mSocket.off("stream start", onStreamStart);
        mSocket.off("stream token", onStreamToken);
        mSocket.off("stream complete", onStreamComplete);
        mSocket.off("stream error", onStreamError);
        mSocket.off("typing", onTyping);
        mSocket.off("stop typing", onStopTyping);
        mSocket.off("login", onAutoLogin);
        mSocket.off("pong", onPong);
        mConnTimeoutHandler.removeCallbacksAndMessages(null);
    }

    @Override
    public void onViewCreated(View view, Bundle savedInstanceState) {
        super.onViewCreated(view, savedInstanceState);

        mMessagesView = (RecyclerView) view.findViewById(R.id.messages);
        mMessagesView.setLayoutManager(new LinearLayoutManager(getActivity()));
        mMessagesView.setAdapter(mAdapter);

        mEmptyChat = (TextView) view.findViewById(R.id.empty_chat);
        mCharacterNameTv = (TextView) view.findViewById(R.id.character_name_tv);
        mConnectionStatus = (TextView) view.findViewById(R.id.connection_status);
        mSettingsButton = (ImageButton) view.findViewById(R.id.settings_button);
        mHelpButton = (ImageButton) view.findViewById(R.id.help_button);
        mCopyButton = (ImageButton) view.findViewById(R.id.copy_button);
        mExtraOptionsButton = (ImageButton) view.findViewById(R.id.extra_options_button);
        mChatBackground = (ImageView) view.findViewById(R.id.chat_background);
        mHeaderAvatar = (ImageView) view.findViewById(R.id.header_avatar);
        mHeaderAvatarEmoji = (TextView) view.findViewById(R.id.header_avatar_emoji);

        mBannerAdContainer = (FrameLayout) view.findViewById(R.id.banner_ad_container);

        // Show banner ad if not premium
        ChatApplication app = (ChatApplication) requireActivity().getApplication();
        mAdManager = app.getAdManager();
        if (!app.getPremiumManager().isPremium()) {
            mAdManager.showBanner(requireActivity(), mBannerAdContainer);
        } else {
            mBannerAdContainer.setVisibility(View.GONE);
        }

        Bundle args = getArguments();
        if (args != null) {
            if (args.containsKey("character_id")) mCharacterId = args.getString("character_id");
            if (args.containsKey("character_name")) mCharacterName = args.getString("character_name");
            if (args.containsKey("character_image")) mCharacterImageUrl = args.getString("character_image");
            if (args.containsKey("character_avatar_image")) mCharacterAvatarImage = args.getString("character_avatar_image");
            if (args.containsKey("character_emoji")) mCharacterEmoji = args.getString("character_emoji");
        }
        if (mCharacterId == null) mCharacterId = mPrefs.getCharacterId();
        if (mCharacterName == null) {
            mCharacterName = mCharacterId != null ? mCharacterId : getString(R.string.app_name);
        }
        updateCharacterNameHeader();
        updateHeaderAvatar();
        if (mAdapter instanceof MessageAdapter) {
            ((MessageAdapter) mAdapter).setCharacterId(mCharacterId);
        }
        loadLocalMessages();

        // Load character background image
        loadCharacterBackground();

        // Handle initial message from questions
        if (args != null && args.containsKey("initial_message")) {
            String initialMessage = args.getString("initial_message");
            if (initialMessage != null && !initialMessage.isEmpty()) {
                // Send the initial message after a short delay to ensure UI is ready
                mInputMessageView.post(() -> {
                    mInputMessageView.setText(initialMessage);
                    attemptSend();
                });
            }
        }

        mCopyButton.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                copyChatToClipboard();
            }
        });

        mSettingsButton.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                showSettingsDialog();
            }
        });

        mHelpButton.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                showCommandsDialog();
            }
        });

        ImageButton backButton = (ImageButton) view.findViewById(R.id.back_button);
        backButton.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                if (getActivity() != null) {
                    getActivity().onBackPressed();
                }
            }
        });

        mConnectionStatus.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                showConnectionDialog();
            }
        });

        mExtraOptionsButton.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                showExtraOptionsSheet();
            }
        });

        mInputMessageView = (EditText) view.findViewById(R.id.message_input);
        mInputMessageView.setOnEditorActionListener(new TextView.OnEditorActionListener() {
            @Override
            public boolean onEditorAction(TextView v, int id, KeyEvent event) {
                if (id == R.id.send || id == EditorInfo.IME_NULL) {
                    attemptSend();
                    return true;
                }
                return false;
            }
        });
        mInputMessageView.addTextChangedListener(new TextWatcher() {
            @Override
            public void beforeTextChanged(CharSequence s, int start, int count, int after) {
            }

            @Override
            public void onTextChanged(CharSequence s, int start, int before, int count) {
            }

            @Override
            public void afterTextChanged(Editable s) {
            }
        });

        ImageButton sendButton = (ImageButton) view.findViewById(R.id.send_button);
        sendButton.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                attemptSend();
            }
        });

        mMicButton = (ImageButton) view.findViewById(R.id.mic_button);
        mMicButton.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                if (mIsRecording) {
                    stopRecording();
                } else {
                    startRecording();
                }
            }
        });

        mImageAttachButton = (ImageButton) view.findViewById(R.id.image_attach_button);
        ImageButton suggestionButton = view.findViewById(R.id.suggestion_button);
        mImagePreview = (ImageView) view.findViewById(R.id.image_preview);
        View imgContainer = view.findViewById(R.id.image_preview_container);
        if (imgContainer != null) imgContainer.setVisibility(View.GONE);
        mImageAttachButton.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                Intent intent = new Intent(Intent.ACTION_PICK, MediaStore.Images.Media.EXTERNAL_CONTENT_URI);
                startActivityForResult(intent, REQUEST_PICK_IMAGE);
            }
        });

        suggestionButton.setOnClickListener(v -> {
            if (mCharacterId == null || mCharacterId.isEmpty()) {
                if (!isAdded()) return;
                Toast.makeText(getActivity(), "Nessun personaggio selezionato", Toast.LENGTH_SHORT).show();
                return;
            }

            suggestionButton.setAlpha(0.5f);
            suggestionButton.setEnabled(false);

            new Thread(() -> {
                try {
                    String token = mAuth.getAccessToken();
                    URL url = new URL(mPrefs.getServerUrl() + "/chat/suggestion");
                    HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                    conn.setRequestMethod("POST");
                    conn.setRequestProperty("Authorization", "Bearer " + token);
                    conn.setRequestProperty("Content-Type", "application/json");
                    conn.setDoOutput(true);
                    conn.setConnectTimeout(8000);

                    JSONObject body = new JSONObject();
                    body.put("character_id", mCharacterId);

                    java.io.OutputStream os = conn.getOutputStream();
                    os.write(body.toString().getBytes());
                    os.close();

                    BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                    StringBuilder resp = new StringBuilder();
                    String line;
                    while ((line = reader.readLine()) != null) resp.append(line);
                    reader.close();
                    conn.disconnect();

                    JSONObject result = new JSONObject(resp.toString());
                    String suggestion = result.optString("suggestion", "");

                    safeRunOnUiThread(() -> {
                        suggestionButton.setAlpha(1.0f);
                        suggestionButton.setEnabled(true);
                        if (!suggestion.isEmpty()) {
                            mInputMessageView.setText(suggestion);
                            mInputMessageView.setSelection(suggestion.length());
                            mInputMessageView.requestFocus();
                        } else {
                            if (!isAdded()) return;
                            Toast.makeText(getActivity(), "Nessun suggerimento disponibile", Toast.LENGTH_SHORT).show();
                        }
                    });
                } catch (Exception e) {
                    safeRunOnUiThread(() -> {
                        suggestionButton.setAlpha(1.0f);
                        suggestionButton.setEnabled(true);
                        if (!isAdded()) return;
                        Toast.makeText(getActivity(), "Errore: " + e.getMessage(), Toast.LENGTH_SHORT).show();
                    });
                }
            }).start();
        });

        View removeImageBtn = view.findViewById(R.id.image_preview_remove);
        if (removeImageBtn != null) {
            removeImageBtn.setOnClickListener(new View.OnClickListener() {
                @Override
                public void onClick(View v) {
                    clearPendingImage();
                }
            });
        }

        View stopBtn = view.findViewById(R.id.stream_stop_button);
        if (stopBtn != null) {
            stopBtn.setVisibility(View.GONE);
            stopBtn.setOnClickListener(new View.OnClickListener() {
                @Override
                public void onClick(View v) {
                    if (mStreaming && mSocket != null) {
                        JSONObject payload = new JSONObject();
                        try {
                            payload.put("user_id", mUserId);
                        } catch (JSONException e) {}
                        mSocket.emit("stream stop", payload);
                        showStreamStopButton(false);
                        if (!isAdded()) return;
                        Toast.makeText(getActivity(), "Generazione interrotta", Toast.LENGTH_SHORT).show();
                    }
                }
            });
        }

        final View inputArea = view.findViewById(R.id.input_area);
        ViewCompat.setOnApplyWindowInsetsListener(view, (v, insets) -> {
            int sysBottom = insets.getInsets(WindowInsetsCompat.Type.systemBars()).bottom;
            int imeBottom = insets.getInsets(WindowInsetsCompat.Type.ime()).bottom;
            int bottomPadding = Math.max(sysBottom, imeBottom);
            inputArea.setPadding(
                inputArea.getPaddingLeft(),
                inputArea.getPaddingTop(),
                inputArea.getPaddingRight(),
                bottomPadding + getResources().getDimensionPixelSize(R.dimen.input_area_extra_padding)
            );
            return WindowInsetsCompat.CONSUMED;
        });

        updateCharacterNameHeader();
        updateConnectionStatus();
    }

    // ---------------------------------------------------------------
    // Character background & extra options
    // ---------------------------------------------------------------

    private void loadCharacterBackground() {
        if (mChatBackground == null || mCharacterImageUrl == null || mCharacterImageUrl.isEmpty()) {
            return;
        }

        new Thread(() -> {
            try {
                java.net.URL url = new java.net.URL(mCharacterImageUrl);
                java.net.HttpURLConnection conn = (java.net.HttpURLConnection) url.openConnection();
                conn.setConnectTimeout(5000);
                conn.setReadTimeout(5000);
                java.io.InputStream is = conn.getInputStream();
                final android.graphics.Bitmap bmp = android.graphics.BitmapFactory.decodeStream(is);
                is.close();
                conn.disconnect();

                if (bmp != null && getActivity() != null) {
                    safeRunOnUiThread(() -> {
                        mChatBackground.setImageBitmap(bmp);
                        mChatBackground.setVisibility(View.VISIBLE);
                    });
                }
            } catch (Exception e) {
                Log.e(TAG, "Failed to load character background: " + e.getMessage());
            }
        }).start();
    }

    private void showExtraOptionsSheet() {
        if (getActivity() == null) return;

        android.app.AlertDialog.Builder builder = new android.app.AlertDialog.Builder(getActivity());
        builder.setTitle("Opzioni Chat");

        String[] options = {
            "Ricomincia chat",
            "Storia della chat",
            "Elimina chat",
            "Gioco",
            "AvatarMix",
            "Bobine",
            "Canzone"
        };

        builder.setItems(options, (dialog, which) -> {
            switch (which) {
                case 0: // Ricomincia chat
                    confirmRestartChat();
                    break;
                case 1: // Storia della chat
                    showChatHistory();
                    break;
                case 2: // Elimina chat
                    confirmDeleteChat();
                    break;
                case 3: // Gioco
                    if (!isAdded()) return;
                    Toast.makeText(getActivity(), "Game Center in arrivo", Toast.LENGTH_SHORT).show();
                    break;
                case 4: // AvatarMix
                    if (!isAdded()) return;
                    Toast.makeText(getActivity(), "AvatarMix in arrivo", Toast.LENGTH_SHORT).show();
                    break;
                case 5: // Bobine
                    if (!isAdded()) return;
                    Toast.makeText(getActivity(), "Bobine in arrivo", Toast.LENGTH_SHORT).show();
                    break;
                case 6: // Canzone
                    if (!isAdded()) return;
                    Toast.makeText(getActivity(), "Canzone in arrivo", Toast.LENGTH_SHORT).show();
                    break;
            }
        });

        builder.show();
    }

    private void confirmRestartChat() {
        new android.app.AlertDialog.Builder(getActivity())
            .setTitle("Ricomincia chat")
            .setMessage("Vuoi cancellare tutti i messaggi e ricominciare?")
            .setPositiveButton("Sì", (d, w) -> {
                if (mLocalDb != null) {
                    mLocalDb.clearMessages(mCharacterId);
                }
                mMessages.clear();
                mAdapter.notifyDataSetChanged();
                updateEmptyState();
                if (!isAdded()) return;
                Toast.makeText(getActivity(), "Chat ricominciata", Toast.LENGTH_SHORT).show();
            })
            .setNegativeButton("No", null)
            .show();
    }

    private void showChatHistory() {
        if (mLocalDb == null) {
            if (!isAdded()) return;
            Toast.makeText(getActivity(), "Storia non disponibile", Toast.LENGTH_SHORT).show();
            return;
        }

        List<JSONObject> history = mLocalDb.getRecentMessages(mCharacterId, 100);
        StringBuilder sb = new StringBuilder();
        for (JSONObject msg : history) {
            try {
                String role = msg.getString("role");
                String content = msg.getString("content");
                sb.append(role.equals("user") ? "Tu" : mCharacterName).append(": ");
                sb.append(content).append("\n\n");
            } catch (Exception ignored) {}
        }

        if (sb.length() == 0) {
            if (!isAdded()) return;
            Toast.makeText(getActivity(), "Nessun messaggio", Toast.LENGTH_SHORT).show();
            return;
        }

        new android.app.AlertDialog.Builder(getActivity())
            .setTitle("Storia della chat")
            .setMessage(sb.toString())
            .setPositiveButton("OK", null)
            .show();
    }

    private void confirmDeleteChat() {
        new android.app.AlertDialog.Builder(getActivity())
            .setTitle("Elimina chat")
            .setMessage("Vuoi eliminare tutti i messaggi? Questa azione non può essere annullata.")
            .setPositiveButton("Elimina", (d, w) -> {
                if (mLocalDb != null) {
                    mLocalDb.clearMessages(mCharacterId);
                }
                mMessages.clear();
                mAdapter.notifyDataSetChanged();
                updateEmptyState();
                if (!isAdded()) return;
                Toast.makeText(getActivity(), "Chat eliminata", Toast.LENGTH_SHORT).show();
            })
            .setNegativeButton("Annulla", null)
            .show();
    }

    private void openGameCenter() {
        Intent intent = new Intent(getActivity(), GameCenterActivity.class);
        startActivity(intent);
    }

    // ---------------------------------------------------------------
    // Connection status management
    // ---------------------------------------------------------------

    private void setConnStage(String stage) {
        mConnStage = stage;
        updateConnectionStatus();
    }

    private void setLastError(String error) {
        mLastError = error;
        Log.e(TAG, "Connection error: " + error);
    }

    private void startConnTimeout() {
        mConnTimeoutHandler.removeCallbacksAndMessages(null);
        mConnTimeoutHandler.postDelayed(new Runnable() {
            @Override
            public void run() {
                if (!mSocketConnected) {
                    setLastError("Timeout connessione");
                    setConnStage("timeout");
                    updateConnectionStatus();
                    if (mEmptyChat != null && mMessages.isEmpty()) {
                        mEmptyChat.setText("Timeout connessione.\nIl server non risponde dopo " + (CONNECTION_TIMEOUT_MS / 1000) + " secondi.");
                        mEmptyChat.setVisibility(View.VISIBLE);
                    }
                }
            }
        }, CONNECTION_TIMEOUT_MS);
    }

    private void updateConnectionStatus() {
        if (mConnectionStatus == null) return;

        String text;
        int color;

        if (mSocketConnected && mRegistered) {
            text = getString(R.string.connection_connected);
            color = getResources().getColor(R.color.status_connected);
        } else if (mLastError != null && !mSocketConnected) {
            text = getString(R.string.conn_error);
            color = getResources().getColor(R.color.status_disconnected);
        } else if (!mConnStage.isEmpty()) {
            switch (mConnStage) {
                case "handshake":
                    text = getString(R.string.conn_handshake);
                    color = getResources().getColor(R.color.status_connecting);
                    break;
                case "connecting":
                    text = getString(R.string.conn_connecting);
                    color = getResources().getColor(R.color.status_connecting);
                    break;
                case "verify_api":
                    text = getString(R.string.conn_verifying_api);
                    color = getResources().getColor(R.color.status_connecting);
                    break;
                case "loading_memory":
                    text = getString(R.string.conn_loading_memory);
                    color = getResources().getColor(R.color.status_connecting);
                    break;
                case "preparing_chat":
                    text = getString(R.string.conn_preparing_chat);
                    color = getResources().getColor(R.color.status_connecting);
                    break;
                case "timeout":
                    text = getString(R.string.conn_timeout);
                    color = getResources().getColor(R.color.status_disconnected);
                    break;
                default:
                    text = getString(R.string.connection_connecting);
                    color = getResources().getColor(R.color.status_connecting);
                    break;
            }
        } else if (mSocket != null && mSocket.connected()) {
            text = getString(R.string.connection_connecting);
            color = getResources().getColor(R.color.status_connecting);
        } else {
            text = getString(R.string.connection_disconnected);
            color = getResources().getColor(R.color.status_disconnected);
        }

        mConnectionStatus.setText(text);
        mConnectionStatus.setBackgroundColor(color);
    }

    private String getConnStageText() {
        if (mSocketConnected && mRegistered) return getString(R.string.conn_ready);
        if (!mConnStage.isEmpty()) {
            switch (mConnStage) {
                case "handshake": return getString(R.string.conn_handshake);
                case "connecting": return getString(R.string.conn_connecting);
                case "verify_api": return getString(R.string.conn_verifying_api);
                case "loading_memory": return getString(R.string.conn_loading_memory);
                case "preparing_chat": return getString(R.string.conn_preparing_chat);
                case "timeout": return getString(R.string.conn_timeout);
            }
        }
        if (mSocket.connected()) return getString(R.string.conn_connecting);
        return getString(R.string.connection_disconnected);
    }

    // ---------------------------------------------------------------
    // Connection status dialog
    // ---------------------------------------------------------------

    private void showConnectionDialog() {
        AlertDialog.Builder builder = new AlertDialog.Builder(getActivity());
        builder.setTitle(null);

        View dialogView = getLayoutInflater().inflate(R.layout.dialog_connection_status, null);
        builder.setView(dialogView);

        final AlertDialog dialog = builder.create();
        dialog.show();

        populateConnectionDialog(dialogView);

        View reconnectBtn = dialogView.findViewById(R.id.btn_reconnect);
        reconnectBtn.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                dialog.dismiss();
                reconnect();
            }
        });
    }

    private void populateConnectionDialog(View dialogView) {
        TextView serverStatus = (TextView) dialogView.findViewById(R.id.status_server);
        TextView apiStatus = (TextView) dialogView.findViewById(R.id.status_api);
        TextView latencyView = (TextView) dialogView.findViewById(R.id.status_latency);
        TextView memoryStatus = (TextView) dialogView.findViewById(R.id.status_memory);
        TextView chatStatus = (TextView) dialogView.findViewById(R.id.status_chat);
        TextView lastErrorView = (TextView) dialogView.findViewById(R.id.status_last_error);
        TextView lastUpdateView = (TextView) dialogView.findViewById(R.id.status_last_update);

        // Server
        if (mSocketConnected) {
            serverStatus.setText("● " + getString(R.string.status_server_connected));
            serverStatus.setTextColor(getResources().getColor(R.color.status_connected));
        } else if (mConnStage.equals("timeout") || mLastError != null) {
            serverStatus.setText("● " + getString(R.string.status_server_disconnected));
            serverStatus.setTextColor(getResources().getColor(R.color.status_disconnected));
        } else {
            serverStatus.setText("● " + getString(R.string.status_server_disconnected));
            serverStatus.setTextColor(getResources().getColor(R.color.status_loading));
        }

        // API
        if (mApiOnline) {
            apiStatus.setText("● " + getString(R.string.status_api_active));
            apiStatus.setTextColor(getResources().getColor(R.color.status_connected));
        } else if (mSocketConnected) {
            apiStatus.setText("● " + getString(R.string.status_api_offline));
            apiStatus.setTextColor(getResources().getColor(R.color.status_warning));
        } else {
            apiStatus.setText("● " + getString(R.string.status_api_offline));
            apiStatus.setTextColor(getResources().getColor(R.color.status_loading));
        }

        // Latency
        latencyView.setText(mLatencyText);

        // Memory
        if (mMemoryLoaded) {
            memoryStatus.setText("● " + getString(R.string.status_memory_loaded));
            memoryStatus.setTextColor(getResources().getColor(R.color.status_connected));
        } else if (mSocketConnected) {
            memoryStatus.setText("● " + getString(R.string.status_memory_loading));
            memoryStatus.setTextColor(getResources().getColor(R.color.status_warning));
        } else {
            memoryStatus.setText("● " + getString(R.string.status_memory_loading));
            memoryStatus.setTextColor(getResources().getColor(R.color.status_loading));
        }

        // Chat
        if (mRegistered) {
            chatStatus.setText("● " + getString(R.string.status_chat_ready));
            chatStatus.setTextColor(getResources().getColor(R.color.status_connected));
        } else if (mSocketConnected) {
            chatStatus.setText("● " + getString(R.string.status_chat_wait));
            chatStatus.setTextColor(getResources().getColor(R.color.status_warning));
        } else {
            chatStatus.setText("● " + getString(R.string.status_chat_wait));
            chatStatus.setTextColor(getResources().getColor(R.color.status_loading));
        }

        // Last error
        if (mLastError != null) {
            lastErrorView.setText(mLastError);
            lastErrorView.setVisibility(View.VISIBLE);
        } else {
            lastErrorView.setText(getString(R.string.status_none));
            lastErrorView.setTextColor(getResources().getColor(R.color.on_surface_dim));
        }

        // Last update
        String time = new SimpleDateFormat("HH:mm:ss", Locale.getDefault()).format(new Date());
        lastUpdateView.setText("Ultimo aggiornamento: " + time);
    }

    // ---------------------------------------------------------------
    // Reconnect
    // ---------------------------------------------------------------

    private void reconnect() {
        mSocketConnected = false;
        mRegistered = false;
        mApiOnline = false;
        mMemoryLoaded = false;
        mLastError = null;
        mLatencyText = "--";
        mConnStage = "handshake";
        setConnStage("handshake");
        startConnTimeout();

        if (mEmptyChat != null && mMessages.isEmpty()) {
            mEmptyChat.setText(getString(R.string.conn_reconnecting));
            mEmptyChat.setVisibility(View.VISIBLE);
        }

        if (getActivity() == null) return;
        ChatApplication app = (ChatApplication) getActivity().getApplication();
        mSocket.disconnect();
        mSocket.off();
        app.reconnect(mPrefs.getServerUrl());
        mSocket = app.getSocket();
        reattachSocketListeners();
        mSocket.connect();
    }

    private void reattachSocketListeners() {
        mSocket.on(Socket.EVENT_CONNECT, onConnect);
        mSocket.on(Socket.EVENT_DISCONNECT, onDisconnect);
        mSocket.on(Socket.EVENT_CONNECT_ERROR, onConnectError);
        mSocket.on("new message", onNewMessage);
        mSocket.on("stream start", onStreamStart);
        mSocket.on("stream token", onStreamToken);
        mSocket.on("stream complete", onStreamComplete);
        mSocket.on("stream error", onStreamError);
        mSocket.on("typing", onTyping);
        mSocket.on("stop typing", onStopTyping);
        mSocket.on("login", onAutoLogin);
        mSocket.on("pong", onPong);
    }

    // ---------------------------------------------------------------
    // UI methods
    // ---------------------------------------------------------------

    private void updateCharacterNameHeader() {
        if (mCharacterNameTv != null) {
            if (mCharacterName != null) {
                mCharacterNameTv.setText(mCharacterName);
            } else {
                mCharacterNameTv.setText(getString(R.string.app_name));
            }
        }
    }

    private void updateHeaderAvatar() {
        if (mHeaderAvatar == null || mHeaderAvatarEmoji == null) return;

        if (mCharacterAvatarImage != null && !mCharacterAvatarImage.isEmpty()) {
            String url = mPrefs.getServerUrl() + "/avatars/" + mCharacterAvatarImage;
            com.bumptech.glide.Glide.with(this)
                .load(url)
                .diskCacheStrategy(com.bumptech.glide.load.engine.DiskCacheStrategy.ALL)
                .placeholder(android.R.color.transparent)
                .error(android.R.color.transparent)
                .into(mHeaderAvatar);
            mHeaderAvatar.setVisibility(View.VISIBLE);
            mHeaderAvatarEmoji.setVisibility(View.GONE);
            return;
        }

        // Fallback: emoji
        mHeaderAvatar.setVisibility(View.GONE);
        mHeaderAvatarEmoji.setVisibility(View.VISIBLE);
        if (mCharacterEmoji != null && !mCharacterEmoji.isEmpty()) {
            mHeaderAvatarEmoji.setText(mCharacterEmoji);
        } else {
            mHeaderAvatarEmoji.setText("👤");
        }
    }

    private void updateEmptyState() {
        if (mEmptyChat != null) {
            mEmptyChat.setVisibility(mMessages.isEmpty() ? View.VISIBLE : View.GONE);
        }
    }

    private void addLog(String message) {
        mMessages.add(new Message.Builder(Message.TYPE_LOG)
                .message(message).build());
        mAdapter.notifyItemInserted(mMessages.size() - 1);
        scrollToBottom();
        updateEmptyState();
    }

    private void addMessage(String username, String message, boolean isRoleplay) {
        addMessage(username, message, isRoleplay, null, null);
    }

    private void addMessage(String username, String message, boolean isRoleplay, String aiProvider, String aiModel) {
        addMessage(username, message, isRoleplay, aiProvider, aiModel, null);
    }

    private void addMessage(String username, String message, boolean isRoleplay, String aiProvider, String aiModel, String imageBase64) {
        addMessage(username, message, isRoleplay, aiProvider, aiModel, imageBase64, null);
    }

    private void addMessage(String username, String message, boolean isRoleplay, String aiProvider, String aiModel, String imageBase64, String videoUrl) {
        int type = isRoleplay ? Message.TYPE_ROLEPLAY : Message.TYPE_MESSAGE;
        Message.Builder builder = new Message.Builder(type)
                .username(username).message(message).isRoleplay(isRoleplay)
                .aiProvider(aiProvider).aiModel(aiModel);
        if (imageBase64 != null && !imageBase64.isEmpty()) {
            builder.imageBase64(imageBase64);
        }
        if (videoUrl != null && !videoUrl.isEmpty()) {
            builder.videoUrl(videoUrl);
        }
        mMessages.add(builder.build());
        mAdapter.notifyItemInserted(mMessages.size() - 1);
        scrollToBottom();
        updateEmptyState();
    }

    private void addTyping(String username) {
        for (int i = mMessages.size() - 1; i >= 0; i--) {
            Message message = mMessages.get(i);
            if (message.getType() == Message.TYPE_ACTION && message.getUsername().equals(username)) {
                return;
            }
        }
        mMessages.add(new Message.Builder(Message.TYPE_ACTION)
                .username(username).build());
        mAdapter.notifyItemInserted(mMessages.size() - 1);
        scrollToBottom();
        updateEmptyState();
    }

    private void addThinking(String username) {
        for (int i = mMessages.size() - 1; i >= 0; i--) {
            Message message = mMessages.get(i);
            if (message.getType() == Message.TYPE_ACTION && message.getUsername().equals(username)) {
                return;
            }
        }
        mMessages.add(new Message.Builder(Message.TYPE_ACTION)
                .username(username)
                .actionText(username + " " + getString(R.string.user_action_thinking))
                .build());
        mAdapter.notifyItemInserted(mMessages.size() - 1);
        scrollToBottom();
        updateEmptyState();
    }

    private void removeTyping(String username) {
        for (int i = mMessages.size() - 1; i >= 0; i--) {
            Message message = mMessages.get(i);
            if (message.getType() == Message.TYPE_ACTION && message.getUsername().equals(username)) {
                mMessages.remove(i);
                mAdapter.notifyItemRemoved(i);
            }
        }
    }

    private JSONObject getUserMemory() {
        if (mLocalDb != null) {
            return mLocalDb.getAllUserMemory();
        }
        return mSessionMemory;
    }

    private void scrollToBottom() {
        mMessagesView.scrollToPosition(mAdapter.getItemCount() - 1);
    }

    private void setAuthHeader(HttpURLConnection conn) {
        String header = mAuth != null ? mAuth.getAuthorizationHeader() : "";
        if (!header.isEmpty()) {
            conn.setRequestProperty("Authorization", header);
        }
    }

    private void attemptSend() {
        if (null == mUsername) return;
        if (!mSocket.connected()) return;
        if (mStreaming) return;

        mTyping = false;

        String message = mInputMessageView.getText().toString().trim();
        boolean hasImage = mPendingImageBase64 != null && !mPendingImageBase64.isEmpty();
        if (TextUtils.isEmpty(message) && !hasImage) {
            mInputMessageView.requestFocus();
            return;
        }

        mInputMessageView.setText("");

        String displayText = message;
        if (hasImage) {
            if (displayText.isEmpty()) displayText = "[Immagine]";
        }
        Message.Builder msgBuilder = new Message.Builder(Message.TYPE_MESSAGE)
                .username(mUsername).message(displayText).isRoleplay(false);
        if (hasImage) {
            msgBuilder.imageBase64(mPendingImageBase64);
        }
        mMessages.add(msgBuilder.build());
        mAdapter.notifyItemInserted(mMessages.size() - 1);
        scrollToBottom();
        updateEmptyState();

        if (mLocalDb != null) {
            mLocalDb.addMessage(mCharacterId, "user", displayText);
        }

        JSONObject payload = new JSONObject();
        try {
            payload.put("message", message);
            payload.put("character", mCharacterId);
            payload.put("user_id", mUserId);

            if (hasImage) {
                payload.put("image", mPendingImageBase64);
                payload.put("image_mime", mPendingImageMime != null ? mPendingImageMime : "image/jpeg");
            }

            if (mLocalDb != null) {
                List<JSONObject> recent = mLocalDb.getRecentMessages(mCharacterId, 20);
                JSONArray ctx = new JSONArray();
                for (JSONObject r : recent) {
                    ctx.put(r);
                }
                payload.put("memory_context", ctx);

                JSONObject userMem = getUserMemory();
                if (userMem.length() > 0) {
                    payload.put("user_memory", userMem);
                }

                payload.put("is_favorite", mLocalDb.isFavorite(mCharacterId));
            }
        } catch (JSONException e) {
            Log.e(TAG, e.getMessage());
        }

        mStreaming = true;
        showStreamStopButton(true);
        addThinking(mCharacterName != null ? mCharacterName : "AI");
        mSocket.emit("stream message", payload);

        // Show interstitial every 8 messages (if not premium)
        if (getActivity() != null && !((ChatApplication) requireActivity().getApplication()).getPremiumManager().isPremium()) {
            mAdManager.onMessageSent(getActivity());
        }

        clearPendingImage();

        JSONObject stopTyping = new JSONObject();
        try {
            stopTyping.put("character", mCharacterId);
        } catch (JSONException e) {
            e.printStackTrace();
        }
        mSocket.emit("stop typing", stopTyping);
    }

    private static final int REQUEST_RECORD_AUDIO = 100;

    private void startRecording() {
        if (getActivity() == null) return;
        if (ContextCompat.checkSelfPermission(getActivity(), Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(getActivity(),
                    new String[]{Manifest.permission.RECORD_AUDIO}, REQUEST_RECORD_AUDIO);
            return;
        }

        try {
            File cacheDir = getActivity().getCacheDir();
            mAudioFilePath = new File(cacheDir, "recording_" + System.currentTimeMillis() + ".3gp").getAbsolutePath();
            mRecorder = new MediaRecorder();
            mRecorder.setAudioSource(MediaRecorder.AudioSource.MIC);
            mRecorder.setOutputFormat(MediaRecorder.OutputFormat.THREE_GPP);
            mRecorder.setAudioEncoder(MediaRecorder.AudioEncoder.AMR_NB);
            mRecorder.setOutputFile(mAudioFilePath);
            mRecorder.prepare();
            mRecorder.start();
            mIsRecording = true;
            mMicButton.setColorFilter(getResources().getColor(R.color.status_disconnected));
            if (!isAdded()) return;
            Toast.makeText(getActivity(), "Registrazione in corso...", Toast.LENGTH_SHORT).show();
        } catch (Exception e) {
            Log.e(TAG, "Failed to start recording", e);
            if (!isAdded()) return;
            Toast.makeText(getActivity(), "Errore avvio registrazione", Toast.LENGTH_SHORT).show();
        }
    }

    private void stopRecording() {
        if (mRecorder != null) {
            try {
                mRecorder.stop();
                mRecorder.release();
            } catch (Exception e) {
                Log.e(TAG, "Error stopping recorder", e);
            }
            mRecorder = null;
        }
        mIsRecording = false;
        mMicButton.clearColorFilter();

        if (mAudioFilePath != null) {
            uploadAudioAndTranscribe(mAudioFilePath);
        }
    }

    private void uploadAudioAndTranscribe(final String filePath) {
        final String baseUrl = mPrefs.getServerUrl();
        if (!isAdded()) return;
        Toast.makeText(getActivity(), "Trascrizione in corso...", Toast.LENGTH_LONG).show();
        new Thread(new Runnable() {
            @Override
            public void run() {
                HttpURLConnection conn = null;
                try {
                    URL url = new URL(baseUrl + "/transcribe");
                    conn = (HttpURLConnection) url.openConnection();
                    conn.setRequestMethod("POST");
                    conn.setConnectTimeout(15000);
                    conn.setReadTimeout(60000);
                    conn.setDoOutput(true);
                    setAuthHeader(conn);
                    conn.setRequestProperty("Content-Type", "audio/3gp");

                    java.io.FileInputStream fis = new java.io.FileInputStream(filePath);
                    java.io.OutputStream os = conn.getOutputStream();
                    byte[] buf = new byte[4096];
                    int n;
                    while ((n = fis.read(buf)) != -1) {
                        os.write(buf, 0, n);
                    }
                    fis.close();
                    os.close();

                    int code = conn.getResponseCode();
                    if (code == 200) {
                        BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                        StringBuilder response = new StringBuilder();
                        String line;
                        while ((line = reader.readLine()) != null) response.append(line);
                        reader.close();
                        final String text = new org.json.JSONObject(response.toString()).optString("text", "");
                        if (!text.isEmpty()) {
                            safeRunOnUiThread(new Runnable() {
                                @Override
                                public void run() {
                                    mInputMessageView.setText(text);
                                    if (!isAdded()) return;
                                    Toast.makeText(getActivity(), "Testo riconosciuto", Toast.LENGTH_SHORT).show();
                                }
                            });
                        } else {
                            safeRunOnUiThread(new Runnable() {
                                @Override
                                public void run() {
                                    if (!isAdded()) return;
                                    Toast.makeText(getActivity(), "Nessun testo riconosciuto", Toast.LENGTH_SHORT).show();
                                }
                            });
                        }
                    } else {
                        safeRunOnUiThread(new Runnable() {
                            @Override
                            public void run() {
                                if (!isAdded()) return;
                                Toast.makeText(getActivity(), "Errore trascrizione (codice " + code + ")", Toast.LENGTH_SHORT).show();
                            }
                        });
                    }
                } catch (Exception e) {
                    Log.e(TAG, "Upload/transcribe error", e);
                    safeRunOnUiThread(new Runnable() {
                        @Override
                        public void run() {
                            if (!isAdded()) return;
                            Toast.makeText(getActivity(), "Errore: " + e.getMessage(), Toast.LENGTH_SHORT).show();
                        }
                    });
                } finally {
                    if (conn != null) conn.disconnect();
                }
            }
        }).start();
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQUEST_RECORD_AUDIO) {
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                startRecording();
            } else {
                if (!isAdded()) return;
                Toast.makeText(getActivity(), "Permesso microfono negato", Toast.LENGTH_SHORT).show();
            }
        }
    }

    @Override
    public void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQUEST_PICK_IMAGE && getActivity() != null && data != null
                && resultCode == getActivity().RESULT_OK) {
            Uri imageUri = data.getData();
            if (imageUri != null) {
                processPickedImage(imageUri);
            }
        }
    }

    private void processPickedImage(Uri imageUri) {
        if (getActivity() == null || imageUri == null) return;
        try {
            Bitmap bitmap = MediaStore.Images.Media.getBitmap(getActivity().getContentResolver(), imageUri);

            int maxDim = 1920;
            int w = bitmap.getWidth();
            int h = bitmap.getHeight();
            if (w > maxDim || h > maxDim) {
                float ratio = Math.min((float) maxDim / w, (float) maxDim / h);
                int nw = Math.round(w * ratio);
                int nh = Math.round(h * ratio);
                bitmap = Bitmap.createScaledBitmap(bitmap, nw, nh, true);
            }

            java.io.ByteArrayOutputStream baos = new java.io.ByteArrayOutputStream();
            bitmap.compress(Bitmap.CompressFormat.JPEG, 85, baos);
            byte[] bytes = baos.toByteArray();
            mPendingImageBase64 = Base64.encodeToString(bytes, Base64.NO_WRAP);
            mPendingImageMime = "image/jpeg";

            if (mImagePreview != null) {
                mImagePreview.setImageBitmap(bitmap);
                View container = getView().findViewById(R.id.image_preview_container);
                if (container != null) container.setVisibility(View.VISIBLE);
            }

            if (!isAdded()) return;
            Toast.makeText(getActivity(), "Immagine allegata", Toast.LENGTH_SHORT).show();
        } catch (Exception e) {
            Log.e(TAG, "Failed to process image", e);
            if (!isAdded()) return;
            Toast.makeText(getActivity(), "Errore elaborazione immagine", Toast.LENGTH_SHORT).show();
        }
    }

    private void clearPendingImage() {
        mPendingImageBase64 = null;
        mPendingImageMime = null;
        View container = getView() != null ? getView().findViewById(R.id.image_preview_container) : null;
        if (container != null) container.setVisibility(View.GONE);
        if (mImagePreview != null) mImagePreview.setImageDrawable(null);
    }

    private void copyChatToClipboard() {
        StringBuilder sb = new StringBuilder();
        String header = "Chat con " + (mCharacterName != null ? mCharacterName : "...");
        sb.append(header).append("\n").append("═══════════════════════════════").append("\n\n");

        for (Message msg : mMessages) {
            String text = msg.getMessage();
            if (text == null || text.isEmpty()) continue;

            if (msg.getType() == Message.TYPE_LOG) {
                sb.append("── ").append(text).append("\n");
            } else if (msg.getType() == Message.TYPE_MESSAGE) {
                sb.append(msg.getUsername()).append(": ").append(text).append("\n\n");
            } else if (msg.getType() == Message.TYPE_ROLEPLAY) {
                sb.append("✦ ").append(msg.getUsername()).append(": ").append(text).append("\n\n");
            }
        }

        if (getActivity() == null) return;
        ClipboardManager clipboard = (ClipboardManager)
                getActivity().getSystemService(Context.CLIPBOARD_SERVICE);
        ClipData clip = ClipData.newPlainText("chat", sb.toString().trim());
        clipboard.setPrimaryClip(clip);
        if (!isAdded()) return;
        Toast.makeText(getActivity(), "Conversazione copiata negli appunti", Toast.LENGTH_SHORT).show();
    }

    private void showCommandsDialog() {
        AlertDialog.Builder builder = new AlertDialog.Builder(getActivity());
        builder.setTitle(getString(R.string.commands_dialog_title));
        View dialogView = getLayoutInflater().inflate(R.layout.dialog_commands, null);
        builder.setView(dialogView);
        builder.setPositiveButton("OK", null);
        builder.show();
    }

    private Map<String, List<String>> mProviderModels = new HashMap<>();
    private List<String> mProviderIds = new ArrayList<>();
    private String mPendingProvider;
    private String mPendingModel;

    private void showSettingsDialog() {
        AlertDialog.Builder builder = new AlertDialog.Builder(getActivity());
        builder.setTitle(getString(R.string.action_settings));

        View dialogView = getLayoutInflater().inflate(R.layout.dialog_settings, null);
        builder.setView(dialogView);

        final EditText urlInput = (EditText) dialogView.findViewById(R.id.dialog_server_url);
        urlInput.setText(mPrefs.getServerUrl());

        final Spinner providerSpinner = (Spinner) dialogView.findViewById(R.id.dialog_provider_spinner);
        final Spinner modelSpinner = (Spinner) dialogView.findViewById(R.id.dialog_model_spinner);
        View refreshBtn = dialogView.findViewById(R.id.dialog_refresh_models);
        View testBtn = dialogView.findViewById(R.id.dialog_test_model);

        // Load current saved provider/model
        final String savedProvider = mPrefs.getProvider();
        final String savedModel = mPrefs.getModel();

        // Populate providers from backend
        loadProvidersIntoSpinner(providerSpinner, modelSpinner, savedProvider, savedModel);

        // When provider changes, update models
        providerSpinner.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(AdapterView<?> parent, View view, int position, long id) {
                String providerId = mProviderIds.get(position);
                updateModelSpinner(modelSpinner, providerId, savedModel);
            }

            @Override
            public void onNothingSelected(AdapterView<?> parent) {}
        });

        refreshBtn.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                refreshModelsFromServer(providerSpinner, modelSpinner, savedModel);
            }
        });

        testBtn.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                String providerId = providerSpinner.getSelectedItemPosition() >= 0 &&
                        providerSpinner.getSelectedItemPosition() < mProviderIds.size()
                        ? mProviderIds.get(providerSpinner.getSelectedItemPosition()) : null;
                if (providerId != null && !providerId.equals("auto")) {
                    testProviderConnection(providerId);
                } else {
                    if (!isAdded()) return;
                    Toast.makeText(getActivity(), "Seleziona un provider specifico", Toast.LENGTH_SHORT).show();
                }
            }
        });

        builder.setPositiveButton("Salva", new android.content.DialogInterface.OnClickListener() {
            @Override
            public void onClick(android.content.DialogInterface dialog, int which) {
                String newUrl = urlInput.getText().toString().trim();
                if (!newUrl.isEmpty() && !newUrl.equals(mPrefs.getServerUrl())) {
                    mPrefs.setServerUrl(newUrl);
                }

                int provPos = providerSpinner.getSelectedItemPosition();
                int modelPos = modelSpinner.getSelectedItemPosition();
                if (provPos >= 0 && provPos < mProviderIds.size()) {
                    String selProvider = mProviderIds.get(provPos);
                    String selModel = null;
                    if (modelPos >= 0 && modelSpinner.getAdapter() != null &&
                            modelSpinner.getAdapter().getCount() > modelPos) {
                        String modelLabel = (String) modelSpinner.getItemAtPosition(modelPos);
                        if (!modelLabel.equals("Auto") && !modelLabel.startsWith("Caricamento")) {
                            selModel = getModelIdForProvider(selProvider, modelPos);
                        }
                    }
                    if (selProvider != null && !selProvider.equals("auto")) {
                        mPrefs.setProvider(selProvider);
                        if (selModel != null) {
                            mPrefs.setModel(selModel);
                        }
                        saveConfigToServer(selProvider, selModel);
                    } else {
                        mPrefs.setProvider("auto");
                        mPrefs.setModel("auto");
                        saveConfigToServer("auto", "auto");
                    }
                }

                if (!newUrl.isEmpty() && !newUrl.equals(mPrefs.getServerUrl())) {
                    reconnect();
                }
            }
        });

        builder.setNegativeButton("Annulla", null);
        builder.show();
    }

    private void loadProvidersIntoSpinner(final Spinner providerSpinner, final Spinner modelSpinner,
                                           final String savedProvider, final String savedModel) {
        final String baseUrl = mPrefs.getServerUrl();
        new Thread(new Runnable() {
            @Override
            public void run() {
                HttpURLConnection conn = null;
                try {
                    URL url = new URL(baseUrl + "/available-models");
                    conn = (HttpURLConnection) url.openConnection();
                    conn.setConnectTimeout(5000);
                    conn.setReadTimeout(5000);
                    setAuthHeader(conn);
                    conn.setRequestProperty("Accept", "application/json");
                    if (conn.getResponseCode() != 200) {
                        setFallbackProviders(providerSpinner, modelSpinner, savedProvider, savedModel);
                        return;
                    }
                    BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                    StringBuilder response = new StringBuilder();
                    String line;
                    while ((line = reader.readLine()) != null) response.append(line);
                    reader.close();

                    JSONObject available = new JSONObject(response.toString());
                    final List<String> providerIds = new ArrayList<>();
                    final List<String> providerNames = new ArrayList<>();
                    final Map<String, List<String>> providerModels = new HashMap<>();

                    providerIds.add("auto");
                    providerNames.add("Auto (catena automatica)");

                    Iterator<String> keys = available.keys();
                    while (keys.hasNext()) {
                        String pid = keys.next();
                        JSONArray models = available.getJSONArray(pid);
                        if (models.length() == 0) continue;
                        String displayName = pid;
                        if (pid.equals("groq")) displayName = "Groq";
                        else if (pid.equals("gemini")) displayName = "Gemini";
                        else if (pid.equals("openrouter")) displayName = "OpenRouter";
                        else if (pid.equals("mistral")) displayName = "Mistral AI";
                        else if (pid.equals("github")) displayName = "GitHub Models";
                        else if (pid.equals("huggingface")) displayName = "Hugging Face";
                        else if (pid.equals("ollama")) displayName = "Ollama (Locale)";
                        providerIds.add(pid);
                        providerNames.add(displayName);
                        List<String> modelList = new ArrayList<>();
                        for (int i = 0; i < models.length(); i++) {
                            JSONObject m = models.getJSONObject(i);
                            modelList.add(m.getString("id"));
                        }
                        providerModels.put(pid, modelList);
                    }

                    safeRunOnUiThread(new Runnable() {
                        @Override
                        public void run() {
                            mProviderIds = providerIds;
                            mProviderModels = providerModels;
                            ArrayAdapter<String> adapter = new ArrayAdapter<>(
                                    getActivity(), android.R.layout.simple_spinner_item, providerNames);
                            adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
                            providerSpinner.setAdapter(adapter);

                            int selProvIdx = savedProvider != null && !savedProvider.equals("auto")
                                    ? providerIds.indexOf(savedProvider) : 0;
                            if (selProvIdx < 0) selProvIdx = 0;
                            providerSpinner.setSelection(selProvIdx);
                            updateModelSpinner(modelSpinner, savedProvider, savedModel);
                        }
                    });
                } catch (Exception e) {
                    setFallbackProviders(providerSpinner, modelSpinner, savedProvider, savedModel);
                } finally {
                    if (conn != null) conn.disconnect();
                }
            }
        }).start();
    }

    private void setFallbackProviders(final Spinner providerSpinner, final Spinner modelSpinner,
                                       final String savedProvider, final String savedModel) {
        safeRunOnUiThread(new Runnable() {
            @Override
            public void run() {
                List<String> ids = new ArrayList<>();
                List<String> names = new ArrayList<>();
                ids.add("auto");
                names.add("Auto (catena automatica)");
                ids.add("ollama");
                names.add("Ollama (Locale)");
                ids.add("groq");
                names.add("Groq");
                ids.add("gemini");
                names.add("Gemini");
                ids.add("openrouter");
                names.add("OpenRouter");
                ids.add("mistral");
                names.add("Mistral AI");
                ids.add("github");
                names.add("GitHub Models");
                ids.add("huggingface");
                names.add("Hugging Face");
                mProviderIds = ids;
                ArrayAdapter<String> adapter = new ArrayAdapter<>(
                        getActivity(), android.R.layout.simple_spinner_item, names);
                adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
                providerSpinner.setAdapter(adapter);
                int idx = savedProvider != null ? ids.indexOf(savedProvider) : 0;
                providerSpinner.setSelection(idx < 0 ? 0 : idx);
                if (!isAdded()) return;
                Toast.makeText(getActivity(), "Server non raggiungibile, lista offline", Toast.LENGTH_SHORT).show();
            }
        });
    }

    private void updateModelSpinner(final Spinner modelSpinner, final String providerId, final String savedModel) {
        if (providerId == null || providerId.equals("auto")) {
            ArrayAdapter<String> adapter = new ArrayAdapter<>(
                    getActivity(), android.R.layout.simple_spinner_item,
                    new String[]{"Auto"});
            adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
            modelSpinner.setAdapter(adapter);
            return;
        }
        List<String> modelIds = mProviderModels.get(providerId);
        if (modelIds == null) {
            modelIds = new ArrayList<>();
        }
        final List<String> finalModelIds = modelIds;
        safeRunOnUiThread(new Runnable() {
            @Override
            public void run() {
                ArrayAdapter<String> adapter = new ArrayAdapter<>(
                        getActivity(), android.R.layout.simple_spinner_item, finalModelIds);
                adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
                modelSpinner.setAdapter(adapter);
                int idx = savedModel != null ? finalModelIds.indexOf(savedModel) : 0;
                modelSpinner.setSelection(idx < 0 ? 0 : idx);
            }
        });
    }

    private String getModelIdForProvider(String providerId, int position) {
        List<String> models = mProviderModels.get(providerId);
        if (models != null && position >= 0 && position < models.size()) {
            return models.get(position);
        }
        return null;
    }

    private void refreshModelsFromServer(final Spinner providerSpinner, final Spinner modelSpinner, final String savedModel) {
        final String baseUrl = mPrefs.getServerUrl();
        if (!isAdded()) return;
        Toast.makeText(getActivity(), "Aggiorno modelli...", Toast.LENGTH_SHORT).show();
        new Thread(new Runnable() {
            @Override
            public void run() {
                HttpURLConnection conn = null;
                try {
                    URL url = new URL(baseUrl + "/refresh-models");
                    conn = (HttpURLConnection) url.openConnection();
                    conn.setRequestMethod("POST");
                    conn.setConnectTimeout(5000);
                    conn.setReadTimeout(5000);
                    setAuthHeader(conn);
                    conn.setRequestProperty("Accept", "application/json");
                    conn.setDoOutput(true);
                    conn.getOutputStream().write("{}".getBytes());
                    if (conn.getResponseCode() == 200) {
                        BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                        StringBuilder response = new StringBuilder();
                        String line;
                        while ((line = reader.readLine()) != null) response.append(line);
                        reader.close();
                        JSONObject result = new JSONObject(response.toString());
                        final String chain = result.optString("chain", "");
                        safeRunOnUiThread(new Runnable() {
                            @Override
                            public void run() {
                                if (!isAdded()) return;
                                Toast.makeText(getActivity(), "Modelli aggiornati: " + chain, Toast.LENGTH_LONG).show();
                                loadProvidersIntoSpinner(providerSpinner, modelSpinner,
                                        mPrefs.getProvider(), mPrefs.getModel());
                            }
                        });
                    } else {
                        safeRunOnUiThread(new Runnable() {
                            @Override
                            public void run() {
                                if (!isAdded()) return;
                                Toast.makeText(getActivity(), "Errore aggiornamento modelli", Toast.LENGTH_SHORT).show();
                            }
                        });
                    }
                } catch (Exception e) {
                    safeRunOnUiThread(new Runnable() {
                        @Override
                        public void run() {
                            Toast.makeText(getActivity(), "Errore: " + e.getMessage(), Toast.LENGTH_SHORT).show();
                        }
                    });
                } finally {
                    if (conn != null) conn.disconnect();
                }
            }
        }).start();
    }

    private void saveConfigToServer(String provider, String model) {
        final String baseUrl = mPrefs.getServerUrl();
        final String uid = mUserId;
        new Thread(new Runnable() {
            @Override
            public void run() {
                HttpURLConnection conn = null;
                try {
                    URL url = new URL(baseUrl + "/config");
                    conn = (HttpURLConnection) url.openConnection();
                    conn.setRequestMethod("POST");
                    conn.setConnectTimeout(5000);
                    conn.setReadTimeout(5000);
                    setAuthHeader(conn);
                    conn.setRequestProperty("Content-Type", "application/json");
                    conn.setDoOutput(true);
                    JSONObject body = new JSONObject();
                    body.put("user_id", uid != null ? uid : "anonymous");
                    body.put("provider", provider);
                    if (model != null) body.put("model", model);
                    OutputStream os = conn.getOutputStream();
                    os.write(body.toString().getBytes());
                    os.close();
                    conn.getResponseCode();
                } catch (Exception e) {
                    Log.e(TAG, "Save config error: " + e.getMessage());
                } finally {
                    if (conn != null) conn.disconnect();
                }
            }
        }).start();
    }

    private void testProviderConnection(final String providerId) {
        final String baseUrl = mPrefs.getServerUrl();
        if (!isAdded()) return;
        Toast.makeText(getActivity(), "Test " + providerId + "...", Toast.LENGTH_SHORT).show();
        new Thread(new Runnable() {
            @Override
            public void run() {
                HttpURLConnection conn = null;
                try {
                    URL url = new URL(baseUrl + "/api/test");
                    conn = (HttpURLConnection) url.openConnection();
                    conn.setRequestMethod("POST");
                    conn.setConnectTimeout(10000);
                    conn.setReadTimeout(10000);
                    setAuthHeader(conn);
                    conn.setRequestProperty("Content-Type", "application/json");
                    conn.setDoOutput(true);
                    JSONObject body = new JSONObject();
                    body.put("provider", providerId);
                    body.put("api_key", mPrefs.getApiKey(providerId));
                    OutputStream os = conn.getOutputStream();
                    os.write(body.toString().getBytes());
                    os.close();
                    if (conn.getResponseCode() == 200) {
                        BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                        StringBuilder response = new StringBuilder();
                        String line;
                        while ((line = reader.readLine()) != null) response.append(line);
                        reader.close();
                        JSONObject result = new JSONObject(response.toString());
                        final boolean success = result.optBoolean("success", false);
                        final String message = result.optString("message", "");
                        safeRunOnUiThread(new Runnable() {
                            @Override
                            public void run() {
                                if (!isAdded()) return;
                                Toast.makeText(getActivity(),
                                        (success ? "OK: " : "Errore: ") + message,
                                        Toast.LENGTH_LONG).show();
                            }
                        });
                    } else {
                        safeRunOnUiThread(new Runnable() {
                            @Override
                            public void run() {
                                if (!isAdded()) return;
                                Toast.makeText(getActivity(), "Errore connessione server", Toast.LENGTH_SHORT).show();
                            }
                        });
                    }
                } catch (Exception e) {
                    safeRunOnUiThread(new Runnable() {
                        @Override
                        public void run() {
                            if (!isAdded()) return;
                            Toast.makeText(getActivity(), "Errore: " + e.getMessage(), Toast.LENGTH_SHORT).show();
                        }
                    });
                } finally {
                    if (conn != null) conn.disconnect();
                }
            }
        }).start();
    }

    // ---------------------------------------------------------------
    // Socket event handlers
    // ---------------------------------------------------------------

    private Emitter.Listener onConnect = new Emitter.Listener() {
        @Override
        public void call(Object... args) {
            safeRunOnUiThread(new Runnable() {
                @Override
                public void run() {
                    mSocketConnected = true;
                    mConnTimeoutHandler.removeCallbacksAndMessages(null);
                    setConnStage("verify_api");
                    mPingStartTime = System.currentTimeMillis();
                    mSocket.emit("ping");

                    if (mUsername == null) {
                        mUsername = mPrefs.getUsername();
                        if (mUsername == null || mUsername.isEmpty()) {
                            mUsername = "user_" + System.currentTimeMillis();
                            mPrefs.setUsername(mUsername);
                        }
                        mUserId = mPrefs.getUsername();
                    }

                    if (mCharacterId == null) {
                        mCharacterId = mPrefs.getCharacterId();
                    }

                    JSONObject data = new JSONObject();
                    try {
                        data.put("username", mUsername);
                        data.put("character", mCharacterId);
                        data.put("user_id", mUserId);
                        mSocket.emit("add user", data);
                    } catch (JSONException e) {
                        e.printStackTrace();
                    }

                    if (mEmptyChat != null) {
                        mEmptyChat.setText("Connesso al server. Attendere...");
                    }
                }
            });
        }
    };

    private Emitter.Listener onDisconnect = new Emitter.Listener() {
        @Override
        public void call(Object... args) {
            safeRunOnUiThread(new Runnable() {
                @Override
                public void run() {
                    Log.i(TAG, "disconnected");
                    mSocketConnected = false;
                    mRegistered = false;
                    setLastError("Connessione persa");
                    setConnStage("");
                    updateConnectionStatus();
                    if (mEmptyChat != null && mMessages.isEmpty()) {
                        mEmptyChat.setText("Disconnesso. Verifica la connessione.");
                        mEmptyChat.setVisibility(View.VISIBLE);
                    }
                }
            });
        }
    };

    private Emitter.Listener onConnectError = new Emitter.Listener() {
        @Override
        public void call(Object... args) {
            safeRunOnUiThread(new Runnable() {
                @Override
                public void run() {
                    String detail = "Impossibile raggiungere il server";
                    if (args != null && args.length > 0) {
                        if (args[0] instanceof Exception) {
                            String msg = ((Exception) args[0]).getMessage();
                            if (msg != null) {
                                if (msg.contains("timeout")) {
                                    detail = getString(R.string.conn_timeout);
                                } else if (msg.contains("refused") || msg.contains("ECONNREFUSED")) {
                                    detail = getString(R.string.conn_server_unreachable);
                                } else {
                                    detail = msg;
                                }
                            }
                        } else {
                            detail += ": " + args[0];
                        }
                    }
                    Log.e(TAG, "Connect error: " + detail);
                    mSocketConnected = false;
                    setLastError(detail);
                    setConnStage("");
                    updateConnectionStatus();
                    mConnTimeoutHandler.removeCallbacksAndMessages(null);
                    if (mEmptyChat != null && mMessages.isEmpty()) {
                        mEmptyChat.setText(detail + "\nVerifica che il backend sia acceso e l'URL corretto.");
                        mEmptyChat.setVisibility(View.VISIBLE);
                    }
                }
            });
        }
    };

    private Emitter.Listener onAutoLogin = new Emitter.Listener() {
        @Override
        public void call(Object... args) {
            safeRunOnUiThread(new Runnable() {
                @Override
                public void run() {
                    JSONObject data = (JSONObject) args[0];
                    try {
                        mUsername = data.getString("username");
                        mUserId = data.getString("user_id");
                        mCharacterId = data.getString("character_id");
                        mCharacterName = data.getString("character_name");
                        if (mAdapter instanceof MessageAdapter) {
                            ((MessageAdapter) mAdapter).setCharacterId(mCharacterId);
                        }
                        mRegistered = true;
                        mApiOnline = true;

                        setConnStage("loading_memory");

                        updateCharacterNameHeader();

                        mMemoryLoaded = true;
                        setConnStage("preparing_chat");

                        addLog(getResources().getString(R.string.message_welcome) + " " + mCharacterName);

                        setConnStage("");
                        updateConnectionStatus();

                        if (mPrefs.getProvider().equals("auto") && mMessages.isEmpty()) {
                            new Handler(Looper.getMainLooper()).postDelayed(new Runnable() {
                                @Override
                                public void run() {
                                    showModelSelectionPrompt();
                                }
                            }, 800);
                        }
                    } catch (JSONException e) {
                        e.printStackTrace();
                    }
                }
            });
        }
    };

    private void showModelSelectionPrompt() {
        AlertDialog.Builder builder = new AlertDialog.Builder(getActivity());
        builder.setTitle("Seleziona modello AI");
        builder.setMessage("Scegli un provider e modello per questa chat.\nPuoi cambiarlo in qualsiasi momento dalle impostazioni.");
        builder.setPositiveButton("Scegli modello", new android.content.DialogInterface.OnClickListener() {
            @Override
            public void onClick(android.content.DialogInterface dialog, int which) {
                showSettingsDialog();
            }
        });
        builder.setNegativeButton("Usa automatico", null);
        builder.show();
    }

    private Emitter.Listener onPong = new Emitter.Listener() {
        @Override
        public void call(Object... args) {
            safeRunOnUiThread(new Runnable() {
                @Override
                public void run() {
                    if (mPingStartTime > 0) {
                        long latency = System.currentTimeMillis() - mPingStartTime;
                        mLatencyText = latency + " ms";
                        mPingStartTime = 0;
                    }
                }
            });
        }
    };

    private void loadLocalMessages() {
        if (mLocalDb == null) return;
        String fallbackUser = mUsername != null ? mUsername : "Tu";
        List<JSONObject> history = mLocalDb.getRecentMessages(mCharacterId, 1000);
        for (JSONObject msg : history) {
            try {
                String role = msg.getString("role");
                String content = msg.getString("content");
                boolean isAI = "assistant".equals(role);
                addMessage(isAI ? mCharacterName : fallbackUser, content, isAI);
            } catch (Exception ignored) {}
        }
    }

    private Emitter.Listener onNewMessage = new Emitter.Listener() {
        @Override
        public void call(final Object... args) {
            safeRunOnUiThread(new Runnable() {
                @Override
                public void run() {
                    JSONObject data = (JSONObject) args[0];
                    String username;
                    String message;
                    boolean isRoleplay = false;
                    String aiProvider = null;
                    String aiModel = null;
                    try {
                        username = data.getString("username");
                        message = data.getString("message");
                        if (data.has("is_roleplay")) {
                            isRoleplay = data.getBoolean("is_roleplay");
                        }
                        if (data.has("ai_provider")) {
                            aiProvider = data.optString("ai_provider", null);
                        }
                        if (data.has("ai_model")) {
                            aiModel = data.optString("ai_model", null);
                        }
                    } catch (JSONException e) {
                        Log.e(TAG, e.getMessage());
                        return;
                    }

                    removeTyping(username);
                    removeTyping(mCharacterName != null ? mCharacterName : "AI");

                    if (!isRoleplay && username.equals(mUsername)) {
                        return;
                    }

                    boolean isFallback = data.has("is_fallback") && data.optBoolean("is_fallback", false);

                    if (isFallback) {
                        addLog(getString(R.string.fallback_unavailable));
                        return;
                    }

                    String generatedImage = data.optString("generated_image", null);
                    String generatedVideo = data.optString("generated_video", null);
                    addMessage(username, message, isRoleplay, aiProvider, aiModel, generatedImage, generatedVideo);

                    if ((generatedImage != null || generatedVideo != null) && mStreaming) {
                        mStreamingMessage = null;
                        mStreamingPosition = -1;
                        mStreaming = false;
                        showStreamStopButton(false);
                    }

                    if (isRoleplay && mLocalDb != null) {
                        mLocalDb.addMessage(mCharacterId, "assistant", message);

                        if (data.has("memory_updates")) {
                            try {
                                JSONObject updates = data.getJSONObject("memory_updates");
                                Iterator<String> keys = updates.keys();
                                while (keys.hasNext()) {
                                    String key = keys.next();
                                    String value = updates.getString(key);
                                    mLocalDb.setUserMemory(key, value);
                                    mSessionMemory.put(key, value);
                                }
                            } catch (JSONException e) {
                                Log.e(TAG, "Error saving memory updates: " + e.getMessage());
                            }
                        }

                        if (data.has("evo_updates")) {
                            try {
                                JSONObject evo = data.getJSONObject("evo_updates");
                                if (evo.has("new_stage") && !evo.isNull("new_stage")) {
                                    String stage = evo.getString("new_stage");
                                    addLog(getString(R.string.evo_new_stage) + " " + stage);
                                }
                                if (evo.has("unlocked")) {
                                    JSONArray unlocked = evo.getJSONArray("unlocked");
                                    for (int i = 0; i < unlocked.length(); i++) {
                                        addLog(getString(R.string.evo_unlocked) + " " + unlocked.getString(i));
                                    }
                                }
                            } catch (JSONException e) {
                                Log.e(TAG, "Error processing evolution: " + e.getMessage());
                            }
                            cacheEvolution();
                        }
                    }
                }
            });
        }
    };

    private void showStreamStopButton(boolean show) {
        View btn = getView() != null ? getView().findViewById(R.id.stream_stop_button) : null;
        if (btn != null) btn.setVisibility(show ? View.VISIBLE : View.GONE);
    }

    private Emitter.Listener onStreamStart = new Emitter.Listener() {
        @Override
        public void call(Object... args) {
            safeRunOnUiThread(new Runnable() {
                @Override
                public void run() {
                    removeTyping(mCharacterName != null ? mCharacterName : "AI");
                    JSONObject data = (JSONObject) args[0];
                    String username = data.optString("username", mCharacterName != null ? mCharacterName : "AI");
                    mStreamingMessage = new Message.Builder(Message.TYPE_ROLEPLAY)
                            .username(username).message("").isRoleplay(true).build();
                    mMessages.add(mStreamingMessage);
                    mStreamingPosition = mMessages.size() - 1;
                    mAdapter.notifyItemInserted(mStreamingPosition);
                    scrollToBottom();
                }
            });
        }
    };

    private Emitter.Listener onStreamToken = new Emitter.Listener() {
        @Override
        public void call(Object... args) {
            safeRunOnUiThread(new Runnable() {
                @Override
                public void run() {
                    JSONObject data = (JSONObject) args[0];
                    String text = data.optString("text", "");
                    if (mStreamingMessage != null && mStreamingPosition >= 0) {
                        mMessages.set(mStreamingPosition, new Message.Builder(Message.TYPE_ROLEPLAY)
                                .username(mStreamingMessage.getUsername())
                                .message(text).isRoleplay(true).build());
                        mStreamingMessage = mMessages.get(mStreamingPosition);
                        mAdapter.notifyItemChanged(mStreamingPosition);
                        scrollToBottom();
                    }
                }
            });
        }
    };

    private Emitter.Listener onStreamComplete = new Emitter.Listener() {
        @Override
        public void call(Object... args) {
            safeRunOnUiThread(new Runnable() {
                @Override
                public void run() {
                    JSONObject data = (JSONObject) args[0];
                    removeTyping(mCharacterName != null ? mCharacterName : "AI");
                    String message = data.optString("message", "");
                    String username = data.optString("username", mCharacterName != null ? mCharacterName : "AI");
                    String aiProvider = data.optString("ai_provider", null);
                    String aiModel = data.optString("ai_model", null);
                    boolean isFallback = data.optBoolean("is_fallback", false);

                    String generatedImage = data.optString("generated_image", null);
                    String generatedVideo = data.optString("generated_video", null);

                    if (mStreamingPosition >= 0) {
                        Message.Builder builder = new Message.Builder(Message.TYPE_ROLEPLAY)
                                .username(username).message(message).isRoleplay(true)
                                .aiProvider(aiProvider).aiModel(aiModel);
                        if (generatedImage != null) builder.imageBase64(generatedImage);
                        if (generatedVideo != null) builder.videoUrl(generatedVideo);
                        mMessages.set(mStreamingPosition, builder.build());
                        mAdapter.notifyItemChanged(mStreamingPosition);
                    }

                    if (mLocalDb != null && message != null && !message.isEmpty()) {
                        mLocalDb.addMessage(mCharacterId, "assistant", message);
                    }

                    if (isFallback && getActivity() != null) {
                        Toast.makeText(getActivity(),
                                "Modello AI non disponibile, risposta generica",
                                Toast.LENGTH_SHORT).show();
                    }

                    mStreamingMessage = null;
                    mStreamingPosition = -1;
                    mStreaming = false;
                    showStreamStopButton(false);
                    scrollToBottom();
                }
            });
        }
    };

    private Emitter.Listener onStreamError = new Emitter.Listener() {
        @Override
        public void call(Object... args) {
            safeRunOnUiThread(new Runnable() {
                @Override
                public void run() {
                    removeTyping(mCharacterName != null ? mCharacterName : "AI");
                    JSONObject data = (JSONObject) args[0];
                    String error = data.optString("message", "Errore sconosciuto");

                    if (mStreamingPosition >= 0) {
                        String currentText = mStreamingMessage != null ? mStreamingMessage.getMessage() : "";
                        Message msg = new Message.Builder(Message.TYPE_ROLEPLAY)
                                .username(mStreamingMessage != null ? mStreamingMessage.getUsername() : "AI")
                                .message(currentText + "\n\n[ERRORE: " + error + "]")
                                .isRoleplay(true).build();
                        mMessages.set(mStreamingPosition, msg);
                        mAdapter.notifyItemChanged(mStreamingPosition);
                    }

                    if (!isAdded()) return;
                    Toast.makeText(getActivity(), "Errore stream: " + error, Toast.LENGTH_LONG).show();

                    mStreamingMessage = null;
                    mStreamingPosition = -1;
                    mStreaming = false;
                    showStreamStopButton(false);
                }
            });
        }
    };

    private Emitter.Listener onTyping = new Emitter.Listener() {
        @Override
        public void call(final Object... args) {
            safeRunOnUiThread(new Runnable() {
                @Override
                public void run() {
                    JSONObject data = (JSONObject) args[0];
                    String username;
                    try {
                        username = data.getString("username");
                    } catch (JSONException e) {
                        Log.e(TAG, e.getMessage());
                        return;
                    }
                    addTyping(username);
                }
            });
        }
    };

    private Emitter.Listener onStopTyping = new Emitter.Listener() {
        @Override
        public void call(final Object... args) {
            safeRunOnUiThread(new Runnable() {
                @Override
                public void run() {
                    JSONObject data = (JSONObject) args[0];
                    String username;
                    try {
                        username = data.getString("username");
                    } catch (JSONException e) {
                        Log.e(TAG, e.getMessage());
                        return;
                    }
                    removeTyping(username);
                }
            });
        }
    };

    private void cacheEvolution() {
        if (mPrefs == null || mCharacterId == null || mUserId == null) return;
        final String uid = mUserId;
        final String cid = mCharacterId;
        final String baseUrl = mPrefs.getServerUrl();
        new Thread(() -> {
            HttpURLConnection conn = null;
            try {
                URL url = new URL(baseUrl + "/evolution?user_id=" + uid + "&character_id=" + cid);
                conn = (HttpURLConnection) url.openConnection();
                conn.setConnectTimeout(5000);
                conn.setReadTimeout(5000);
                setAuthHeader(conn);
                conn.setRequestProperty("Accept", "application/json");
                if (conn.getResponseCode() != 200) return;
                BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                StringBuilder response = new StringBuilder();
                String line;
                while ((line = reader.readLine()) != null) response.append(line);
                reader.close();
                JSONObject obj = new JSONObject(response.toString());
                JSONObject evo = obj.optJSONObject("evolution");
                if (evo != null) {
                    evo.put("user_id", uid);
                    evo.put("character_id", cid);
                    if (mLocalDb != null) {
                        mLocalDb.saveEvolution(evo);
                    }
                }
            } catch (Exception ignored) {
            } finally {
                if (conn != null) conn.disconnect();
            }
        }).start();
    }

    private Runnable onTypingTimeout = new Runnable() {
        @Override
        public void run() {
            if (!mTyping) return;

            mTyping = false;
            JSONObject data = new JSONObject();
            try {
                data.put("character", mCharacterId);
            } catch (JSONException e) {
                e.printStackTrace();
            }
            mSocket.emit("stop typing", data);
        }
    };
}