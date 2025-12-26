/**
 * ai 回复时，对于某些内容，需要展示特定的组件，在这里进行组件的注册和调用
 */

export interface ComponentToolRequestItem {
  name: string;
  whenCondition: "and" | "or"; // 当条件为 and 时，所有条件都满足时才展示组件；当条件为 or 时，只要有一个条件满足时就展示组件
  when: {
    tool_names?: string[]; // 当 mcp 工具名称匹配时，后端才会组装对应的组件
    tool_call_content?: string[]; // 当 mcp 工具调用内容匹配时，后端才会组装对应的组件
    user_message_content?: string[]; // 当用户消息内容匹配时，后端才会组装对应的组件
    assistant_message_content?: string[]; // 当 ai 消息内容匹配时，后端才会组装对应的组件
  };
}

export interface ComponentToolItem extends ComponentToolRequestItem {
  component:
    | React.ComponentType<any>
    | React.LazyExoticComponent<React.ComponentType<any>>;
  typeSourceFile: string; // 组件类型定义的文件路径
}
