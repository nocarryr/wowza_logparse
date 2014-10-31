loadedInterfaceName = "template";

interfaceOrientation = "portrait";

pages = [[
{
    "name": "refresh",
    "type": "Button",
    "x": 0.6, "y": 0.9,
    "width": 0.2, "height": 0.1,
    "startingValue": 0,
    "isLocal": true,
    "mode": "contact",
    "stroke": "#aaa"
},
{
    "name": "refreshLabel",
    "type": "Label",
    "x": 0.6, "y": 0.9,
    "width": 0.2, "height": 0.1,
    "isLocal": true,
    "value": "refresh"
},
{
    "name": "tabButton",
    "type": "Button",
    "x": 0.8, "y": 0.9,
    "width": 0.2, "height": 0.1,
    "mode": "toggle",
    "stroke": "#aaa",
    "isLocal": true,
    "ontouchstart": "if(this.value == this.max) { control.showToolbar(); } else { control.hideToolbar(); }"
},
{
    "name": "tabButtonLabel",
    "type": "Label",
    "x": 0.8, "y": 0.9,
    "width": 0.2, "height": 0.1,
    "mode": "contact",
    "isLocal": true,
    "value": "menu"
}

]

];
