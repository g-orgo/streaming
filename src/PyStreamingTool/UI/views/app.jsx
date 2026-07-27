// import MenuItem from "../components/menu_container"

function App() {
    const menus_disponiveis = [{ name: "Legendas", icon: "🆎" }];
    const [active_menu, setActiveMenu] = React.useState(null);

    return (
        <div className="flex flex-col gap-8 w-full h-full">
            <h1>Configurações de PyStreamingTool:</h1>

            <div className="flex justify-between items-center h-full min-w-[50%] w-full gap-3">
                {menus_disponiveis.map((item) => (
                    <MenuItem
                        name={item.name}
                        icon={item.icon}
                        onClick={() => setActiveMenu(item)}
                    />
                ))}
                <div className="w-full h-full rounded-xl bg-red-50 border border-red-100 p-10">
                    {active_menu ? (
                        <h3>{active_menu.name}</h3>
                    ) : (
                        <h1>"Nenhum menu selecionado"</h1>
                    )}
                </div>
            </div>
        </div>
    );
}

const root = ReactDOM.createRoot(document.querySelector("#app"));
root.render(<App />);
