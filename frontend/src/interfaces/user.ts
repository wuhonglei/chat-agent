export interface UserInfo {
  id: string;
  name: string;
  avatar?: string;
  phone: string;
}

export enum UserProfileItemType {
  Fact = 1, // 事实
  Preference = 2, // 偏好
}

/** 用户画像单条：事实或偏好 */
export interface UserProfileItem {
  id: string;
  text: string;
  type: UserProfileItemType;
  createdAt: string;
}

/** 用户画像列表：facts 与 preferences */
export interface UserProfileList {
  facts: UserProfileItem[];
  preferences: UserProfileItem[];
}
