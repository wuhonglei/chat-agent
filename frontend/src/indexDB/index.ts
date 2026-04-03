import { DB_NAME, DB_VERSION } from "@/constants";
import { ChatConversationState } from "@/interfaces";
import Dexie, { Table } from "dexie";

export interface ConversationMessages {
  id: string;
  data: ChatConversationState;
}

class IndexDB extends Dexie {
  conversationMessages!: Table<ConversationMessages>;

  constructor(dbName: string) {
    super(dbName);
    this.version(1).stores({
      conversationMessages: "id, data",
    });
    this.version(DB_VERSION)
      .stores({
        conversationMessages: "id, data",
      })
      .upgrade(async tx => {
        await tx.table("conversationMessages").clear();
      });
  }
}

export const db = new IndexDB(DB_NAME);
