import React, { ReactNode } from 'react'
import { Layout, Menu, Button, MenuProps } from 'antd'
import { useNavigate, useLocation } from 'react-router-dom'
import {
  MessageOutlined,
  FileTextOutlined,
  DatabaseOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from '@ant-design/icons'
import { useAppDispatch, useAppSelector } from '../../store/hooks'
import { toggleSidebar } from '../../store/slices/uiSlice'

const { Header, Sider } = Layout

interface MainLayoutProps {
  children: ReactNode
}

const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  const navigate = useNavigate()
  const location = useLocation()
  const dispatch = useAppDispatch()
  const { sidebarCollapsed } = useAppSelector((state) => state.ui)

  const menuItems: MenuProps['items'] = [
    {
      key: '/',
      icon: <MessageOutlined />,
      label: '智能问答',
    },
    {
      key: '/documents',
      icon: <FileTextOutlined />,
      label: '文档管理',
    },
    {
      key: '/knowledge-base',
      icon: <DatabaseOutlined />,
      label: '知识库',
    },
  ]

  const handleMenuClick: MenuProps['onClick'] = ({ key }) => {
    navigate(key)
  }

  return (
    <Layout className="min-h-screen">
      <Sider
        trigger={null}
        collapsible
        collapsed={sidebarCollapsed}
        className="bg-white shadow-md"
      >
        <div className="h-16 flex items-center justify-center border-b">
          <h1 className={`font-bold text-lg text-primary-600 ${sidebarCollapsed ? 'text-sm' : ''}`}>
            {sidebarCollapsed ? 'AI' : 'AI Doc Q&A'}
          </h1>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={handleMenuClick}
          className="border-r-0"
        />
      </Sider>
      <Layout>
        <Header className="bg-white px-4 shadow-sm flex items-center">
          <Button
            type="text"
            icon={sidebarCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => dispatch(toggleSidebar())}
            className="text-lg"
          />
          <span className="ml-4 text-lg font-medium">智能文档问答系统</span>
        </Header>
        {children}
      </Layout>
    </Layout>
  )
}

export default MainLayout