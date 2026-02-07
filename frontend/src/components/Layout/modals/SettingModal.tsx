import { UserInfo } from "@/interfaces";
import { Modal } from "antd";
import { useRef, useState } from "react";
import AccountManage, { AccountManageRef } from "../components/AccountManage";

type Props = {
  open: boolean;
  onCancel: () => void;
  data: UserInfo | null;
};

export default function SettingModal({ open, onCancel, data }: Props) {
  const accountManageRef = useRef<AccountManageRef>(null);
  const [loading, setLoading] = useState(false);
  const okButtonLoading = open && loading;

  const handleOk = () => {
    accountManageRef.current?.submit();
  };

  return (
    <Modal
      centered
      open={open}
      title="用户设置"
      onOk={handleOk}
      onCancel={onCancel}
      okButtonProps={{ loading: okButtonLoading }}
    >
      <AccountManage
        ref={accountManageRef}
        data={data}
        onSuccess={() => {
          setTimeout(onCancel, 300);
        }}
        onLoadingChange={setLoading}
      />
    </Modal>
  );
}
