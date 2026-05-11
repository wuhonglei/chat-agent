import { useState } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from './assets/vite.svg'
import heroImg from './assets/hero.png'
import './App.css'

function App() {
  const [count, setCount] = useState(0)

  return (
    <main id="center">
      <div className="hero">
        <img src={heroImg} className="base" width="170" height="179" alt="" />
        <img src={reactLogo} className="framework" alt="React logo" />
        <img src={viteLogo} className="vite" alt="Vite logo" />
      </div>

      <h1>React + Vite 起步页</h1>
      <p>
        编辑 <code>src/App.tsx</code> 并保存，即可看到热更新效果。
      </p>

      <button
        type="button"
        className="counter"
        onClick={() => setCount((prev) => prev + 1)}
      >
        当前计数：{count}
      </button>

      <nav aria-label="常用链接">
        <ul>
          <li>
            <a href="https://vite.dev/" target="_blank" rel="noreferrer">
              <img className="logo" src={viteLogo} alt="" />
              Vite 文档
            </a>
          </li>
          <li>
            <a href="https://react.dev/" target="_blank" rel="noreferrer">
              <img className="button-icon" src={reactLogo} alt="" />
              React 文档
            </a>
          </li>
        </ul>
      </nav>
    </main>
  )
}

export default App
