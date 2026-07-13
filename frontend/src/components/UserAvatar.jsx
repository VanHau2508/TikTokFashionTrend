import React from "react";

function UserAvatar({ user, size = 44 }) {
  const avatarUrl = user?.avatar_url;
  const username = user?.username || "U";
  const letter = username.charAt(0).toUpperCase();

  return (
    <div
      className="user-avatar-pro"
      style={{
        width: size,
        height: size,
        minWidth: size,
      }}
    >
      {avatarUrl ? (
        <img src={avatarUrl} alt={username} />
      ) : (
        <span>{letter}</span>
      )}
    </div>
  );
}

export default UserAvatar;