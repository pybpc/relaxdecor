buttons = [QPushButton(f'Button {i}') for i in range(10)]


@buttons[0].clicked.connect
def spam():
    ...


@buttons[1].clicked.connect
def eggs():
    ...


button_0 = buttons[0]


@button_0.clicked.connect
def spam():
    ...


button_1 = buttons[1]


@button_1.clicked.connect
def eggs():
    ...
