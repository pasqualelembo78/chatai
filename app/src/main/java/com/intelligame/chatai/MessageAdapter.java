package com.intelligame.chatai;

import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Typeface;
import android.net.Uri;
import android.util.Base64;
import androidx.recyclerview.widget.RecyclerView;
import android.text.SpannableStringBuilder;
import android.text.style.StyleSpan;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ImageButton;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;


public class MessageAdapter extends RecyclerView.Adapter<MessageAdapter.ViewHolder> {

    private List<Message> mMessages;
    private int[] mUsernameColors;
    private Context mContext;
    private String mCharacterId;

    public MessageAdapter(Context context, List<Message> messages) {
        mMessages = messages;
        mContext = context;
        mUsernameColors = context.getResources().getIntArray(R.array.username_colors);
    }

    public void setCharacterId(String characterId) {
        mCharacterId = characterId;
    }

    @Override
    public ViewHolder onCreateViewHolder(ViewGroup parent, int viewType) {
        int layout;
        switch (viewType) {
            case Message.TYPE_MESSAGE:
                layout = R.layout.item_message;
                break;
            case Message.TYPE_LOG:
                layout = R.layout.item_log;
                break;
            case Message.TYPE_ACTION:
                layout = R.layout.item_action;
                break;
            case Message.TYPE_ROLEPLAY:
                layout = R.layout.item_message;
                break;
            default:
                layout = R.layout.item_message;
        }
        View v = LayoutInflater
                .from(parent.getContext())
                .inflate(layout, parent, false);
        return new ViewHolder(v);
    }

    @Override
    public void onBindViewHolder(ViewHolder viewHolder, int position) {
        Message message = mMessages.get(position);

        if (message.getType() == Message.TYPE_ROLEPLAY) {
            viewHolder.setRoleplayMessage(message.getMessage());
        } else {
            viewHolder.setMessage(message.getMessage());
        }
        viewHolder.setUsername(message.getUsername());
        viewHolder.setProviderInfo(message.getAiProvider(), message.getAiModel());

        String username = message.getUsername();
        Context ctx = viewHolder.itemView.getContext();
        String myUsername = null;
        try {
            ChatApplication app = (ChatApplication) ctx.getApplicationContext();
            myUsername = app.getPrefs().getUsername();
        } catch (Exception e) {
        }

        boolean isMine = myUsername != null && myUsername.equals(username);
        boolean isRoleplay = message.getType() == Message.TYPE_ROLEPLAY;

        viewHolder.setBubbleStyle(isMine, isRoleplay);
        viewHolder.setupPlayButton(message, isRoleplay, mCharacterId);
        viewHolder.setMessageImage(message.getImageBase64());
        viewHolder.setupVideoLink(message);
        viewHolder.setupReportButton(message, mCharacterId);
        viewHolder.setupCopyButton(message);
    }

    @Override
    public int getItemCount() {
        return mMessages.size();
    }

    @Override
    public int getItemViewType(int position) {
        return mMessages.get(position).getType();
    }

    public class ViewHolder extends RecyclerView.ViewHolder {
        private TextView mUsernameView;
        private TextView mMessageView;
        private TextView mProviderInfoView;
        private LinearLayout mContainer;
        private ImageButton mPlayButton;
        private ImageView mMessageImage;
        private ImageButton mReportButton;
        private ImageButton mCopyButton;

        public ViewHolder(View itemView) {
            super(itemView);

            mUsernameView = (TextView) itemView.findViewById(R.id.username);
            mMessageView = (TextView) itemView.findViewById(R.id.message);
            mProviderInfoView = (TextView) itemView.findViewById(R.id.provider_info);
            mContainer = (LinearLayout) itemView.findViewById(R.id.message_container);
            mPlayButton = (ImageButton) itemView.findViewById(R.id.play_audio);
            mMessageImage = (ImageView) itemView.findViewById(R.id.message_image);
            mReportButton = (ImageButton) itemView.findViewById(R.id.btn_report_message);
            mCopyButton = (ImageButton) itemView.findViewById(R.id.btn_copy_message);
        }

        public void setMessageImage(String imageBase64) {
            if (mMessageImage == null) return;
            if (imageBase64 != null && !imageBase64.isEmpty()) {
                try {
                    byte[] bytes = Base64.decode(imageBase64, Base64.DEFAULT);
                    Bitmap bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.length);
                    mMessageImage.setImageBitmap(bitmap);
                    mMessageImage.setVisibility(View.VISIBLE);
                } catch (Exception e) {
                    mMessageImage.setVisibility(View.GONE);
                }
            } else {
                mMessageImage.setVisibility(View.GONE);
            }
        }

        public void setupVideoLink(final Message message) {
            String videoUrl = message.getVideoUrl();
            if (videoUrl != null && !videoUrl.isEmpty() && mMessageView != null) {
                final String fullUrl;
                if (videoUrl.startsWith("http")) {
                    fullUrl = videoUrl;
                } else {
                    ChatApplication app = (ChatApplication) mContext.getApplicationContext();
                    fullUrl = app.getPrefs().getServerUrl() + videoUrl;
                }
                mMessageView.setOnClickListener(new View.OnClickListener() {
                    @Override
                    public void onClick(View v) {
                        try {
                            Intent i = new Intent(Intent.ACTION_VIEW, Uri.parse(fullUrl));
                            mContext.startActivity(i);
                        } catch (Exception e) {
                            Toast.makeText(mContext, "Impossibile aprire il video", Toast.LENGTH_SHORT).show();
                        }
                    }
                });
                mMessageView.setText(message.getMessage() + "\n\n▶️ Tocca per guardare il video");
            } else if (mMessageView != null) {
                mMessageView.setOnClickListener(null);
            }
        }

        public void setUsername(String username) {
            if (null == mUsernameView) return;
            mUsernameView.setText(username);
            mUsernameView.setTextColor(getUsernameColor(username));
        }

        public void setMessage(String message) {
            if (null == mMessageView) return;
            mMessageView.setText(message);
            mMessageView.setTypeface(Typeface.DEFAULT);
            mMessageView.setTextColor(0xFF000000);
        }

        public void setRoleplayMessage(String message) {
            if (null == mMessageView) return;
            SpannableStringBuilder sb = new SpannableStringBuilder();
            Pattern pattern = Pattern.compile("\\*([^*]+)\\*");
            Matcher matcher = pattern.matcher(message);
            int lastEnd = 0;
            while (matcher.find()) {
                sb.append(message.substring(lastEnd, matcher.start()));
                int start = sb.length();
                sb.append(matcher.group(1));
                sb.setSpan(new StyleSpan(Typeface.ITALIC), start, sb.length(), 0);
                lastEnd = matcher.end();
            }
            sb.append(message.substring(lastEnd));
            mMessageView.setText(sb);
            mMessageView.setTypeface(Typeface.DEFAULT);
            mMessageView.setTextColor(0xFF000000);
        }

        public void setProviderInfo(String provider, String model) {
            if (mProviderInfoView == null) return;
            boolean hasProvider = provider != null && !provider.isEmpty();
            boolean hasModel = model != null && !model.isEmpty();
            if (hasProvider || hasModel) {
                StringBuilder sb = new StringBuilder("via ");
                if (hasProvider) sb.append(provider);
                if (hasProvider && hasModel) sb.append(" · ");
                if (hasModel) sb.append(model);
                mProviderInfoView.setText(sb.toString());
                mProviderInfoView.setVisibility(View.VISIBLE);
            } else {
                mProviderInfoView.setVisibility(View.GONE);
            }
        }

        public void setBubbleStyle(boolean isMine, boolean isRoleplay) {
            if (mContainer == null || mMessageView == null) return;

            if (isMine) {
                mContainer.setGravity(android.view.Gravity.END);
                mMessageView.setBackgroundResource(R.drawable.bubble_user);
                if (mUsernameView != null) {
                    mUsernameView.setGravity(android.view.Gravity.END);
                }
            } else if (isRoleplay) {
                mContainer.setGravity(android.view.Gravity.START);
                mMessageView.setBackgroundResource(R.drawable.bubble_ai);
                if (mUsernameView != null) {
                    mUsernameView.setGravity(android.view.Gravity.START);
                }
            } else {
                mContainer.setGravity(android.view.Gravity.START);
                mMessageView.setBackgroundResource(R.drawable.bubble_ai);
                if (mUsernameView != null) {
                    mUsernameView.setGravity(android.view.Gravity.START);
                }
            }
        }

        public void setupPlayButton(final Message message, boolean isRoleplay, final String characterId) {
            if (mPlayButton == null) return;
            if (isRoleplay && message.getMessage() != null && !message.getMessage().isEmpty()) {
                mPlayButton.setVisibility(View.VISIBLE);
                mPlayButton.setImageResource(android.R.drawable.ic_media_play);
                mPlayButton.setOnClickListener(new View.OnClickListener() {
                    @Override
                    public void onClick(View v) {
                        v.setEnabled(false);
                        mPlayButton.setImageResource(android.R.drawable.ic_menu_search);
                        new Thread(new Runnable() {
                            @Override
                            public void run() {
                                final boolean success = playTts(message.getMessage(), characterId);
                                if (mPlayButton != null) {
                                    mPlayButton.post(new Runnable() {
                                        @Override
                                        public void run() {
                                            mPlayButton.setEnabled(true);
                                            mPlayButton.setImageResource(android.R.drawable.ic_media_play);
                                        }
                                    });
                                }
                            }
                        }).start();
                    }
                });
            } else {
                mPlayButton.setVisibility(View.GONE);
                mPlayButton.setOnClickListener(null);
            }
        }

        public void setupReportButton(final Message message, final String characterId) {
            if (mReportButton == null) return;
            mReportButton.setOnClickListener(v -> {
                Context ctx = mReportButton.getContext();
                new androidx.appcompat.app.AlertDialog.Builder(ctx)
                    .setTitle("Segnala messaggio")
                    .setMessage("Vuoi segnalare questo messaggio come inappropriato?")
                    .setPositiveButton("Segnala", (dialog, which) -> {
                        reportMessage(ctx, message, characterId);
                    })
                    .setNegativeButton("Annulla", null)
                    .show();
            });
        }

        public void setupCopyButton(final Message message) {
            if (mCopyButton == null) return;
            mCopyButton.setOnClickListener(v -> {
                Context ctx = mCopyButton.getContext();
                ClipboardManager clipboard = (ClipboardManager) ctx.getSystemService(Context.CLIPBOARD_SERVICE);
                ClipData clip = ClipData.newPlainText("message", message.getMessage());
                clipboard.setPrimaryClip(clip);
                Toast.makeText(ctx, "Messaggio copiato", Toast.LENGTH_SHORT).show();
            });
        }

        private void reportMessage(Context ctx, Message message, String characterId) {
            new Thread(() -> {
                try {
                    ChatApplication app = (ChatApplication) ctx.getApplicationContext();
                    String baseUrl = app.getPrefs().getServerUrl();
                    String token = app.getAuthManager().getAccessToken();
                    String userId = app.getPrefs().getUsername();

                    org.json.JSONObject body = new org.json.JSONObject();
                    body.put("reported_by", userId);
                    body.put("character_id", characterId != null ? characterId : "");
                    body.put("message_text", message.getMessage() != null ? message.getMessage() : "");
                    body.put("reported_user", message.getUsername() != null ? message.getUsername() : "");

                    URL url = new URL(baseUrl.replace("/chat", "") + "/user/report");
                    java.net.HttpURLConnection conn = (java.net.HttpURLConnection) url.openConnection();
                    conn.setRequestMethod("POST");
                    conn.setRequestProperty("Authorization", "Bearer " + token);
                    conn.setRequestProperty("Content-Type", "application/json");
                    conn.setDoOutput(true);
                    conn.setConnectTimeout(5000);
                    java.io.OutputStream os = conn.getOutputStream();
                    os.write(body.toString().getBytes());
                    os.close();
                    int code = conn.getResponseCode();
                    conn.disconnect();

                    if (mReportButton != null) {
                        mReportButton.post(() -> {
                            if (code == 200 || code == 201) {
                                android.widget.Toast.makeText(ctx,
                                    "Segnalazione inviata. Grazie.", android.widget.Toast.LENGTH_SHORT).show();
                            } else {
                                // Silenzioso — non mostrare errori all'utente
                            }
                        });
                    }
                } catch (Exception ignored) {}
            }).start();
        }

        private boolean playTts(String text, String characterId) {
            if (text == null || text.isEmpty()) return false;
            Context ctx = mPlayButton.getContext();
            try {
                ChatApplication app = (ChatApplication) ctx.getApplicationContext();
                String baseUrl = app.getPrefs().getServerUrl();

                URL url = new URL(baseUrl + "/tts");
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("POST");
                conn.setConnectTimeout(10000);
                conn.setReadTimeout(30000);
                conn.setRequestProperty("Content-Type", "application/json");
                conn.setDoOutput(true);

                String json = "{\"text\":\"" + jsonEscape(text) + "\",\"character_id\":\"" + (characterId != null ? characterId : "") + "\"}";
                conn.getOutputStream().write(json.getBytes("UTF-8"));

                int code = conn.getResponseCode();
                if (code != 200) {
                    conn.disconnect();
                    return false;
                }

                File cacheDir = ctx.getCacheDir();
                File audioFile = new File(cacheDir, "tts_" + System.currentTimeMillis() + ".wav");
                FileOutputStream fos = new FileOutputStream(audioFile);
                InputStream is = conn.getInputStream();
                byte[] buf = new byte[4096];
                int n;
                while ((n = is.read(buf)) != -1) {
                    fos.write(buf, 0, n);
                }
                fos.close();
                is.close();
                conn.disconnect();

                android.media.MediaPlayer mp = new android.media.MediaPlayer();
                mp.setDataSource(audioFile.getAbsolutePath());
                mp.prepare();
                mp.start();
                mp.setOnCompletionListener(new android.media.MediaPlayer.OnCompletionListener() {
                    @Override
                    public void onCompletion(android.media.MediaPlayer mp) {
                        mp.release();
                        audioFile.delete();
                    }
                });
                return true;
            } catch (Exception e) {
                android.util.Log.e("TTS", "Playback failed", e);
                return false;
            }
        }

        private String jsonEscape(String s) {
            return s.replace("\\", "\\\\")
                    .replace("\"", "\\\"")
                    .replace("\n", "\\n")
                    .replace("\r", "\\r")
                    .replace("\t", "\\t");
        }

        private int getUsernameColor(String username) {
            if (username == null || username.isEmpty()) {
                return 0xFF888888;
            }
            int hash = 7;
            for (int i = 0, len = username.length(); i < len; i++) {
                hash = username.codePointAt(i) + (hash << 5) - hash;
            }
            int index = Math.abs(hash % mUsernameColors.length);
            return mUsernameColors[index];
        }
    }
}
