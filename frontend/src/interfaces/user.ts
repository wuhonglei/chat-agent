export interface UserInfo {
  id: string;
  name: string;
  avatar?: string;
  phone: string;
}

/** 用户画像单条：事实或偏好 */
export interface UserProfileItem {
  id: string;
  text: string;
  /** fact | preference */
  type: string;
  createdAt: string;
}

/** 用户画像列表：facts 与 preferences */
export interface UserProfileList {
  facts: UserProfileItem[];
  preferences: UserProfileItem[];
}
