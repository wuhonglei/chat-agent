import Dexie, { Table } from "dexie";
import { ChatConversationState } from "@/interfaces";
import { DB_NAME, DB_VERSION } from "@/constants";

export interface ConversationMessages {
  id: string;
  data: ChatConversationState;
}

class IndexDB extends Dexie {
  conversationMessages!: Table<ConversationMessages>;

  constructor(dbName: string) {
    super(dbName);
    this.version(DB_VERSION).stores({
      conversationMessages: "id, data",
    });
  }
}

export const db = new IndexDB(DB_NAME);
