package com.intelligame.chatai;

public class Message {

    public static final int TYPE_MESSAGE = 0;
    public static final int TYPE_LOG = 1;
    public static final int TYPE_ACTION = 2;
    public static final int TYPE_ROLEPLAY = 3;

    private int mType;
    private String mMessage;
    private String mUsername;
    private boolean mIsRoleplay;
    private String mAiProvider;
    private String mAiModel;
    private String mAudioUrl;
    private String mImageBase64;
    private String mVideoUrl;
    private String mActionText;

    private Message() {}

    public int getType() {
        return mType;
    };

    public String getMessage() {
        return mMessage;
    };

    public String getUsername() {
        return mUsername;
    };

    public boolean isRoleplay() {
        return mIsRoleplay;
    };

    public String getAiProvider() {
        return mAiProvider;
    };

    public String getAiModel() {
        return mAiModel;
    };

    public String getAudioUrl() {
        return mAudioUrl;
    };

    public String getImageBase64() {
        return mImageBase64;
    };

    public String getVideoUrl() {
        return mVideoUrl;
    };

    public String getActionText() {
        return mActionText;
    };


    public static class Builder {
        private final int mType;
        private String mUsername;
        private String mMessage;
        private boolean mIsRoleplay;
        private String mAiProvider;
        private String mAiModel;
        private String mAudioUrl;
        private String mImageBase64;
        private String mVideoUrl;
        private String mActionText;

        public Builder(int type) {
            mType = type;
        }

        public Builder username(String username) {
            mUsername = username;
            return this;
        }

        public Builder message(String message) {
            mMessage = message;
            return this;
        }

        public Builder isRoleplay(boolean isRoleplay) {
            mIsRoleplay = isRoleplay;
            return this;
        }

        public Builder aiProvider(String aiProvider) {
            mAiProvider = aiProvider;
            return this;
        }

        public Builder aiModel(String aiModel) {
            mAiModel = aiModel;
            return this;
        }

        public Builder audioUrl(String audioUrl) {
            mAudioUrl = audioUrl;
            return this;
        }

        public Builder imageBase64(String imageBase64) {
            mImageBase64 = imageBase64;
            return this;
        }

        public Builder videoUrl(String videoUrl) {
            mVideoUrl = videoUrl;
            return this;
        }

        public Builder actionText(String actionText) {
            mActionText = actionText;
            return this;
        }

        public Message build() {
            Message message = new Message();
            message.mType = mType;
            message.mUsername = mUsername;
            message.mMessage = mMessage;
            message.mIsRoleplay = mIsRoleplay;
            message.mAiProvider = mAiProvider;
            message.mAiModel = mAiModel;
            message.mAudioUrl = mAudioUrl;
            message.mImageBase64 = mImageBase64;
            message.mVideoUrl = mVideoUrl;
            message.mActionText = mActionText;
            return message;
        }
    }
}
