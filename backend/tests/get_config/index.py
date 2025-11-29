from nacos import NacosClient
import json
from dotenv import load_dotenv
import os

load_dotenv()


def get_nacos_config():
    """
    从 Nacos 获取配置的通用方法
    :return: 解析后的配置字典
    """
    # -------------------------- 1. 配置 Nacos 连接信息 --------------------------
    # Nacos 服务地址（多个地址用逗号分隔，如 "ip1:8848,ip2:8848"）
    SERVER_ADDRESSES = os.getenv("NACOS_SERVER_ADDRESSES")
    # 命名空间ID（默认public，自定义命名空间需填ID而非名称）
    NAMESPACE = os.getenv("NACOS_NAMESPACE")
    USERNAME = os.getenv("NACOS_USERNAME")    # Nacos 登录用户名（默认nacos）
    PASSWORD = os.getenv("NACOS_PASSWORD")    # Nacos 登录密码（默认nacos）

    # -------------------------- 2. 配置目标配置信息 --------------------------
    DATA_ID = os.getenv("NACOS_DATA_ID")  # 配置ID（必填）
    GROUP = os.getenv("NACOS_GROUP")  # 配置分组（默认DEFAULT_GROUP）
    # 配置格式（支持：json/yaml/properties/text，根据实际配置选择）
    CONFIG_TYPE = os.getenv("NACOS_CONFIG_TYPE")

    try:
        # -------------------------- 3. 初始化 Nacos 客户端 --------------------------
        # 方式1：基础认证（推荐，Nacos 开启认证时必须）
        client = NacosClient(
            server_addresses=SERVER_ADDRESSES,
            namespace=NAMESPACE,
            username=USERNAME,
            password=PASSWORD
        )

        # 方式2：无认证（仅适用于 Nacos 未开启认证的场景）
        # client = NacosClient(server_addresses=SERVER_ADDRESSES, namespace=NAMESPACE)

        # -------------------------- 4. 获取配置 --------------------------
        # get_config 方法参数：data_id, group, timeout=3（超时时间，单位秒）
        config_content = client.get_config(
            data_id=DATA_ID,
            group=GROUP,
            timeout=5
        )

        if not config_content:
            raise ValueError(
                f"获取配置失败：data_id={DATA_ID}, group={GROUP} 对应的配置不存在")

        # -------------------------- 5. 解析配置（根据 CONFIG_TYPE 适配） --------------------------
        parsed_config = {}
        if CONFIG_TYPE == "json":
            parsed_config = json.loads(config_content)
        elif CONFIG_TYPE == "yaml":
            import yaml
            parsed_config = yaml.safe_load(config_content)
        elif CONFIG_TYPE == "properties":
            # 解析 properties 格式（key=value）
            from io import StringIO
            from configparser import ConfigParser
            config_parser = ConfigParser()
            config_parser.read_string(config_content)
            # properties 无section时默认DEFAULT
            parsed_config = dict(config_parser.items("DEFAULT"))
        else:
            # 文本格式直接返回
            parsed_config = config_content

        print(f"✅ 成功获取 Nacos 配置：")
        print(f"原始配置内容：\n{config_content}\n")
        print(f"解析后配置：\n{parsed_config}")

        return parsed_config

    except Exception as e:
        print(f"❌ 获取 Nacos 配置失败：{str(e)}")
        raise  # 按需决定是否抛出异常


# -------------------------- 6. 测试调用 --------------------------
if __name__ == "__main__":
    nacos_config = get_nacos_config()
    # 后续可通过 nacos_config 访问配置项，例如：
    # print(nacos_config.get("db_url"))
