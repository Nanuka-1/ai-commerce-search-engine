import ChatWidget from './widget/ChatWidget'

// Демо: страница магазина (фон) + наш виджет. На сайте магазина будет только <ChatWidget />.
export default function App() {
  return (
    <>
      <div className="demo-note">
        <b>TopSport — დემო</b>
        <br />
        ჩატი იხსნება მარჯვენა ქვედა კუთხეში 💬
      </div>
      <ChatWidget />
    </>
  )
}
