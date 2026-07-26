// import MenuItem from "../components/menu_container"

function App() {
    const menus_disponiveis = [{ name: "Legendas", icon: "🆎" }];
    const [active_menu, setActiveMenu] = React.useState(null)

    return (
        <div className="flex flex-col gap-8 w-full h-full">
            <h1>Configurações de PyStreamingTool:</h1>

            <div className="flex justify-between items-center h-full">
                <div className="flex flex-col w-[100px]">
                    {menus_disponiveis.map((item) => (
                        <MenuItem
                            name={item.name}
                            icon={item.icon}
                            onClick={() => setActiveMenu(item)}
                        />
                    ))}
                </div>
                <div className="w-full h-full bg-red-500">{JSON.stringify(active_menu) ?? "Nenhum menu selecionado"}</div>
            </div>
        </div>
    );
}

const root = ReactDOM.createRoot(document.querySelector("#app"));
root.render(<App />);
