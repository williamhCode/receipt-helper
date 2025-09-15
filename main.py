from nicegui import ui, events
import os
from dotenv import load_dotenv

people = ["William", "Hao", "Howard"]
people_extern = [False, False, False]

class TabData:
    name: str
    items: list
    rows: list
    costs: dict

    def __init__(self, name, items):
        self.name = name
        self.items = items
        self.rows = [
            {"id": id, "name": name, "price": price, "taxable": taxable}
            for id, (name, price, taxable) in enumerate(items)
        ]
        for person in people:
            for row in self.rows:
                row[person] = False
        self.costs = {person: 0 for person in people}
        self.update_costs()

    def checkbox_change(self, e: events.GenericEventArguments):
        for row in self.rows:
            if row['id'] == e.args['id']:
                row.update(e.args)
        self.update_costs()
        self.display_costs.refresh()

    def update_costs(self):
        tax_rate = 0.07
        for person in people:
            self.costs[person] = 0

        for row in self.rows:
            num_checked = sum(row[person] for person in people)

            price = row["price"] * (1 + tax_rate) if row["taxable"] else row["price"]

            price_per_person = price / (num_checked if num_checked > 0 else people_extern.count(False))

            for person, extern in zip(people, people_extern):
                if (num_checked == 0 and not extern) or row[person]:
                    self.costs[person] += price_per_person

    @ui.refreshable
    def display_list(self, columns):
        with ui.table(title="Grocery Items", columns=columns, rows=self.rows).props("dense").classes("w-auto") as table:
            table.add_slot('body', r'''
                <q-tr :props="props">
                    <q-td key="name" :props="props">
                        {{ props.row.name }}
                    </q-td>
                    <q-td key="price" :props="props">
                        {{ parseFloat(props.row.price).toFixed(2) }}
                    </q-td>
                    <q-td key="taxable" :props="props">
                        {{ props.row.taxable ? "Yes" : "No" }}
                    </q-td>
                    <q-td v-for="person in props.cols.slice(3)" :key="person.name" :props="props">
                        <q-checkbox
                            v-model="props.row[person.name]"
                            @update:model-value="() => $parent.$emit('checkbox_change', props.row)"
                            size="xs"
                        />
                    </q-td>
                </q-tr>
            ''')

            def checkbox_change(e: events.GenericEventArguments):
                self.checkbox_change(e)
                self.display_list.refresh()

            table.on("checkbox_change", checkbox_change)

    @ui.refreshable
    def display_costs(self):
        with ui.card():
            ui.label("Costs").classes("text-h6")
            with ui.grid(columns=2):
                for person in people:
                    ui.label(f"{person}:")
                    ui.label(f"{self.costs[person]:.2f}").classes("text-right")
                ui.label(f"Total:")
                ui.label(f"{sum(self.costs.values()):.2f}").classes("text-right")


def main(): 
    columns = [
        {"name": "name", "label": "Name", "field": "name", "align": "left"},
        {"name": "price", "label": "Price", "field": "price"},
        {"name": "taxable", "label": "Taxed", "field": "taxable", "align": "center"},
        *[{"name": person, "label": person, "field": person, "align": "center"} for person in people]
    ]

    tabs_data = []
        
    with ui.dialog() as dialog, ui.card().style("min-width: 400px"):
        name = ui.input(label='Name')
        data_str = ui.textarea(label='List Data').style("width: 100%")
        def add_tab():
            data = TabData(name.value, eval(data_str.value))
            tabs_data.append(data)
            dialog.close()
            tabs.update()
            tabs_func.refresh()
            tabs.set_value(data.name)
        ui.button("Add").on("click", add_tab)

    @ui.refreshable
    def tabs_func():
        with ui.tabs() as tabs:
            for tab_data in tabs_data:
                ui.tab(tab_data.name)
            ui.element("div").classes("q-pa-sm")
            ui.button(icon="add").on("click", dialog.open)

        with ui.tab_panels(tabs) as panels:
            for tab_data in tabs_data:
                with ui.tab_panel(tab_data.name):
                    with ui.row():
                        tab_data.display_list(columns)
                        tab_data.display_costs()

        return tabs

    tabs = tabs_func()
    # tabs.set_value(tabs_data[0].name)

    load_dotenv()
    token = os.getenv("DEVICE-0_TOKEN")
    ui.run(on_air=token)


if __name__ in {"__main__", "__mp_main__"}:
    main()
