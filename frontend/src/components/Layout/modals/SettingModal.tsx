import AccountManage from "@/components/Layout/components/AccountManage";
import { Modal } from "antd";

type Props = {
  open: boolean;
  onCancel: () => void;
};

export default function SettingModal({ open, onCancel }: Props) {
  return (
    <Modal
      centered
      open={open}
      title="系统设置"
      footer={null}
      onCancel={onCancel}
      width="min(520px, calc(100vw - 32px))"
    >
      <AccountManage />
    </Modal>
  );
}
