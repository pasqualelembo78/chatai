package com.intelligame.chatai;

import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Typeface;
import android.net.Uri;
import android.text.SpannableStringBuilder;
import android.text.style.StyleSpan;
import android.util.Base64;
import android.view.Gravity;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ImageButton;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.PopupMenu;
import android.widget.TextView;
import android.widget.Toast;

import androidx.recyclerview.widget.RecyclerView;

import com.bumptech.glide.Glide;
import com.bumptech.glide.load.resource.bitmap.CircleCrop;
import com.bumptech.glide.request.RequestOptions;

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
    private String mCharacterAvatarUrl;
    private String mCharacterName;

    public MessageAdapter(Context context, List<Message> messages) {
        mMessages = messages;
        mContext = context;
        mUsernameColors = context.getResources().getIntArray(R.array.username_colors);
    }

    public void setCharacterId(String characterId) {
        mCharacterId = characterId;
    }

    public void setCharacterAvatar(String serverUrl, String avatarImage) {
        if (serverUrl != null && avatarImage != null && !avatarImage.isEmpty()) {
            mCharacterAvatarUrl = serverUrl + "/avatars/" + avatarImage;
        } else {
            mCharacterAvatarUrl = null;
        }
    }

    public void setCharacterName(String name) {
        mCharacterName = name;
    }

    @Override
    public ViewHolder onCreateViewHolder(ViewGroup parent, int viewType) {
        int layout;
        switch (viewType) {
            case Message.TYPE_LOG:
                layout = R.layout.item_log;
                break;
            case Message.TYPE_ACTION:
                layout = R.layout.item_action;
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

        if (message.getType() == Message.TYPE_LOG) {
            viewHolder.setLogMessage(message.getMessage());
            return;
        }

        if (message.getType() == Message.TYPE_ACTION) {
            viewHolder.setActionText(message.getActionText());
            return;
        }

        if (message.getType() == Message.TYPE_ROLEPLAY) {
            viewHolder.setRoleplayMessage(message.getMessage());
        } else {
            viewHolder.setMessage(message.getMessage());
        }

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
        viewHolder.setupAvatar(isMine, mCharacterAvatarUrl);
        viewHolder.setupPlayButton(message, isRoleplay, mCharacterId);
        viewHolder.setMessageImage(message.getImageBase64());
        viewHolder.setupVideoLink(message);
        viewHolder.setupLongPress(message, isMine, isRoleplay, mCharacterId);
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
        private ImageView mAvatarView;
        private ImageButton mReportButton;
        private ImageButton mCopyButton;
        private LinearLayout mActionRow;

        public ViewHolder(View itemView) {
            super(itemView);

            mUsernameView = itemView.findViewById(R.id.username);
            mMessageView = itemView.findViewById(R.id.message);
            mProviderInfoView = itemView.findViewById(R.id.provider_info);
            mContainer = itemView.findViewById(R.id.message_container);
            mPlayButton = itemView.findViewById(R.id.play_audio);
            mMessageImage = itemView.findViewById(R.id.message_image);
            mAvatarView = itemView.findViewById(R.id.message_avatar);
            mReportButton = itemView.findViewById(R.id.btn_report_message);
            mCopyButton = itemView.findViewById(R.id.btn_copy_message);
            mActionRow = itemView.findViewById(R.id.action_row);
        }

        public void setupAvatar(boolean isMine, String avatarUrl) {
            if (mAvatarView == null) return;
            if (isMine || avatarUrl == null || avatarUrl.isEmpty()) {
                mAvatarView.setVisibility(View.GONE);
                return;
            }
            mAvatarView.setVisibility(View.VISIBLE);
            Glide.with(itemView.getContext())
                .load(avatarUrl)
                .apply(new RequestOptions().transform(new CircleCrop()))
                .placeholder(android.R.color.transparent)
                .error(android.R.color.transparent)
                .into(mAvatarView);
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
                mMessageView.setOnClickListener(v -> {
                    try {
                        Intent i = new Intent(Intent.ACTION_VIEW, Uri.parse(fullUrl));
                        mContext.startActivity(i);
                    } catch (Exception e) {
                        Toast.makeText(mContext, "Impossibile aprire il video", Toast.LENGTH_SHORT).show();
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
            mMessageView.setTextColor(0xFFFFFFFF);
        }

        public void setLogMessage(String message) {
            if (null == mMessageView) return;
            mMessageView.setText(message);
            mMessageView.setTypeface(Typeface.DEFAULT);
        }

        public void setActionText(String actionText) {
            if (null == mMessageView) return;
            if (actionText != null && !actionText.isEmpty()) {
                mMessageView.setText(actionText);
            } else {
                mMessageView.setText(mContext.getString(R.string.user_action_typing));
            }
            mMessageView.setTypeface(Typeface.DEFAULT);
            mMessageView.setTextColor(mContext.getResources().getColor(R.color.on_surface_dim));
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
            mMessageView.setTextColor(0xFFFFFFFF);
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
                mContainer.setGravity(Gravity.END);
                mMessageView.setBackgroundResource(R.drawable.bubble_user);
                mMessageView.setTextColor(0xFF1E1E2E); // Dark text for white bubble
                if (mUsernameView != null) {
                    mUsernameView.setVisibility(View.GONE);
                }
                if (mAvatarView != null) {
                    mAvatarView.setVisibility(View.GONE);
                }
            } else {
                mContainer.setGravity(Gravity.START);
                mMessageView.setBackgroundResource(R.drawable.bubble_ai);
                mMessageView.setTextColor(0xFFFFFFFF); // White text for dark bubble
                if (mUsernameView != null) {
                    mUsernameView.setVisibility(View.GONE);
                }
            }
        }

        public void setupPlayButton(final Message message, boolean isRoleplay, final String characterId) {
            if (mPlayButton == null) return;
            if (isRoleplay && message.getMessage() != null && !message.getMessage().isEmpty()) {
                mPlayButton.setVisibility(View.VISIBLE);
                mPlayButton.setImageResource(android.R.drawable.ic_media_play);
                mPlayButton.setOnClickListener(v -> {
                    v.setEnabled(false);
                    mPlayButton.setImageResource(android.R.drawable.ic_menu_search);
                    new Thread(() -> {
                        final boolean success = playTts(message.getMessage(), characterId);
                        if (mPlayButton != null) {
                            mPlayButton.post(() -> {
                                mPlayButton.setEnabled(true);
                                mPlayButton.setImageResource(android.R.drawable.ic_media_play);
                            });
                        }
                    }).start();
                });
            } else {
                mPlayButton.setVisibility(View.GONE);
                mPlayButton.setOnClickListener(null);
            }
        }

        public void setupLongPress(final Message message, boolean isMine, boolean isRoleplay, final String characterId) {
            if (mMessageView == null) return;
            mMessageView.setOnLongClickListener(v -> {
                showContextMenu(v, message, isMine, isRoleplay, characterId);
                return true;
            });
        }

        private void showContextMenu(View anchor, final Message message, boolean isMine, boolean isRoleplay, final String characterId) {
            PopupMenu popup = new PopupMenu(anchor.getContext(), anchor);
            popup.getMenu().add(0, 1, 0, "Copia messaggio");
            if (isRoleplay && message.getMessage() != null && !message.getMessage().isEmpty()) {
                popup.getMenu().add(0, 2, 1, "Riproduci audio");
            }
            if (!isMine) {
                popup.getMenu().add(0, 3, 2, "Segnala messaggio");
            }

            popup.setOnMenuItemClickListener(item -> {
                switch (item.getItemId()) {
                    case 1:
                        ClipboardManager clipboard = (ClipboardManager) anchor.getContext().getSystemService(Context.CLIPBOARD_SERVICE);
                        ClipData clip = ClipData.newPlainText("message", message.getMessage());
                        clipboard.setPrimaryClip(clip);
                        Toast.makeText(anchor.getContext(), "Messaggio copiato", Toast.LENGTH_SHORT).show();
                        return true;
                    case 2:
                        new Thread(() -> playTts(message.getMessage(), characterId)).start();
                        return true;
                    case 3:
                        new androidx.appcompat.app.AlertDialog.Builder(anchor.getContext())
                            .setTitle("Segnala messaggio")
                            .setMessage("Vuoi segnalare questo messaggio come inappropriato?")
                            .setPositiveButton("Segnala", (dialog, which) -> reportMessage(anchor.getContext(), message, characterId))
                            .setNegativeButton("Annulla", null)
                            .show();
                        return true;
                }
                return false;
            });
            popup.show();
        }

        private void reportMessage(Context ctx, Message message, String characterId) {
            new Thread(() -> {
                try {
                    ChatApplication app = (ChatApplication) ctx.getApplicationContext();
                    String baseUrl = app.getPrefs().getServerUrl();

                    org.json.JSONObject body = new org.json.JSONObject();
                    body.put("content_type", "message");
                    body.put("content_id", characterId != null ? characterId : "");
                    body.put("reason", "Contenuto inappropriato");
                    body.put("snippet", message.getMessage() != null ? message.getMessage() : "");

                    AuthManager.HttpResponse httpResp = app.getAuthManager().requestWithRefresh(
                        baseUrl + "/report", "POST", body.toString(), 8000);

                    if (httpResp.statusCode >= 200 && httpResp.statusCode < 300) {
                        mReportButton.post(() ->
                            Toast.makeText(ctx, "Segnalazione inviata. Grazie.", Toast.LENGTH_SHORT).show()
                        );
                    }
                } catch (Exception ignored) {}
            }).start();
        }

        private boolean playTts(String text, String characterId) {
            if (text == null || text.isEmpty()) return false;
            Context ctx = itemView.getContext();
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
                mp.setOnCompletionListener(mp1 -> {
                    mp1.release();
                    audioFile.delete();
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
