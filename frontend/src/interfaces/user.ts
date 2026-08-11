export interface UserInfo {
  id: string;
  name: string;
  avatar?: string;
  phone: string;
  /** 用户角色：user / admin */
  role?: string;
}

export enum UserProfileItemType {
  Fact = 1, // 事实
  Preference = 2, // 偏好
}

/** 用户画像单条：事实或偏好 */
export interface UserMemoryItem {
  id: string;
  memory: string;
  type: UserProfileItemType;
  createdAt: string;
}

/** 用户画像列表 */
export interface UserProfileList {
  memories: UserMemoryItem[];
}
