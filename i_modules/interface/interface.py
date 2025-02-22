import copy
import json
from typing import List

from kivy.clock import Clock
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.stencilview import StencilView
from kivy.uix.scatterlayout import ScatterPlaneLayout
from kivy.uix.treeview import TreeViewLabel, TreeView
from kivy.uix.spinner import Spinner
from kivy.uix.tabbedpanel import TabbedPanel
from kivy.uix.scrollview import ScrollView
from kivy.core.window import Window
from kivy.uix.progressbar import ProgressBar
from kivy.graphics import Line, Bezier

from kivy.config import Config

# import datasets_processors.generate_processors
from hyper_variables_forms.hvfs import CriterionForm
from nn_modules.node import NodeLink, Node
from schematics.interface_schematic import InterfaceSchematic
from schematics.node_schematic import NodeSchematic
from node_editor.node_editor import NodeEditor
from utility.custom_action_bar import CustomActionBar
from utility.custom_bezier.custom_bezier import CustomBezier
from utility.rightclick_toolbar.rightclick_toolbar import RightClickMenu
from utility.utils import get_obj, remove_node_from_interface, round_pos, \
    get_bezier_endpoints
from utility.custom_tabbedpanel import TabManager
from utility.custom_input.custom_input import CustomTextInput
from i_modules.interface_actionbar.interface_actionbar import TrainButton, \
    ProgressIndicator, CheckpointButton, TrainedModelLabel, ModeLabel, OpenGraphButton
from nn_modules.code_names import *
from i_modules.stacked_code_template import algorithm as stacked_algorithm

Config.set('input', 'mouse', 'mouse,disable_multitouch')


class InterfaceTabManager(TabManager):
    def __init__(self, **kwargs):
        super(InterfaceTabManager, self).__init__(**kwargs)
        self.previous_tab = None

        Clock.schedule_interval(self.on_switch_tab, 0)

    def on_switch_tab(self, *args):
        if self.previous_tab != self.current_tab:
            try:
                interface = self.current_tab.content.children[0]

                # Load Hierarchy according to the current Interface
                hierarchy = get_obj(self, 'Hierarchy')
                hierarchy.clear_hierarchy()
                hierarchy.load_hierarchy_from_interface(interface)

                # Load HVFS (Hyper Variable FormS) according to the current Interface
                custom_action_bar = get_obj(interface, 'CustomActionBar')
                custom_action_bar.load_hvfs({'hvfs': interface.hvfs},
                                            interface)
            except Exception as e:
                pass

            self.previous_tab = self.current_tab


class SubLayout(BoxLayout):
    def __init__(self, **kwargs):
        super(SubLayout, self).__init__(**kwargs)


class InvisObj(Widget):
    def __init__(self, **kwargs):
        super(InvisObj, self).__init__()
        self.size_hint = (0.3, 0.05)


class CreateBlock(BoxLayout):
    def create_block(self):
        screen_manager = get_obj(self, '_Container').request_obj('Manager')
        component_panel = get_obj(self, '_Container').request_obj('ComponentPanel')

        node_editor = NodeEditor(screen_manager=screen_manager,
                                 component_panel=component_panel)
        node_editor.open()


class GroupNamePopup(Popup):
    def __init__(self, hierarchy, parent_node, node,
                 func, obj, template, currentNodeName, **kwargs):
        super(GroupNamePopup, self).__init__(**kwargs)
        self.title = 'Nodes\' Name'

        self.parent_node = parent_node
        self.node = node
        self.func = func
        self.obj = obj
        self.hierarchy = hierarchy
        self.template = template
        self.currentNodeName = currentNodeName

        self.auto_dismiss = False
        self.size_hint = (0.2, 0.15)

        self.confirmButton = Button(text='Confirm')
        self.confirmButton.bind(on_press=self.confirm)

        self.nameInput = CustomTextInput()

        self.layout = BoxLayout(orientation='vertical')
        self.layout.add_widget(self.nameInput)
        self.layout.add_widget(self.confirmButton)

        self.add_widget(self.layout)

    def confirm(self, obj):
        if self.nameInput.text:
            text = self.nameInput.text
        else:
            text = self.node.name

        self.parent_node.text = self.node.label.text = self.node.name = text
        self.func(self.obj, self.node, self.template, self.currentNodeName)
        self.hierarchy.remove_node_name('Parent Node')
        self.dismiss()


class Hierarchy(TreeView):
    def __init__(self, **kwargs):
        super(Hierarchy, self).__init__(**kwargs)

        self.node_funcs = {
            'Remove Node': self.remove_selected_node
        }

    def on_tree(self, node_name):
        for tree_node in self.iterate_all_nodes():
            if node_name == tree_node.text:
                return True
        return False

    def clear_hierarchy(self):
        for tree_node in self.children:
            self.remove_node(tree_node)

    def remove_node_name(self, node_name):
        for tree_node in self.children:
            if tree_node.text == node_name and tree_node.is_leaf:
                self.remove_node(tree_node)

    def add_tree_node(self, node_name):
        tree_node = TreeViewLabel(text=node_name)
        tree_node.bind(on_touch_down=self.open_rightclick_menu)
        self.add_node(tree_node)

    def load_hierarchy_from_interface(self, interface):
        for node_name in interface.nodes.keys():
            if not self.on_tree(node_name):
                self.add_tree_node(node_name)

    def open_rightclick_menu(self, obj, touch):
        overlay = get_obj(self, 'Overlay')
        overlay.clear_menu()

        if touch.button == 'right' and self.selected_node and self.collide_point(*touch.pos):
            overlay.open_menu(
                RightClickMenu(funcs=self.node_funcs,
                               pos=overlay.to_overlay_coord(touch, self))
            )

    def remove_selected_node(self, obj):
        interface = get_obj(self, 'Interface')
        remove_node_from_interface(interface, self.selected_node.text)

        # Remove Node in the Hierarchy
        self.remove_node(self.selected_node)


class ComponentPanel(ScrollView):
    def __init__(self, **kwargs):
        super(ComponentPanel, self).__init__()
        self.size_hint = (0.2, 1)
        self.tree_view = TreeView(size_hint=(1, None),
                                  hide_root=True)
        self.tree_view.bind(minimum_height=self.tree_view.setter('height'))
        # self.tree_view.root_options = {'text': 'Component Panel'}

        self.norm_nodes_label = TreeViewLabel(text='Normal Nodes')
        self.stacked_nodes_label = TreeViewLabel(text='Stacked Nodes')
        self.function_nodes_label = TreeViewLabel(text='Functions')

        self.node_funcs = {
            'Delete Node': self.delete_node
        }

        self.tree_view.add_node(self.norm_nodes_label)
        self.tree_view.add_node(self.stacked_nodes_label)
        self.tree_view.add_node(self.function_nodes_label)
        self.add_widget(self.tree_view)
        self.update_panel()

    def delete_node(self):
        nodes = json.load(open('./nn_modules/nn_nodes.json'))
        nodes.pop(self.tree_view.selected_node.text)

        open('./nn_modules/nn_nodes.json', 'w').write(
            json.dumps(nodes,
                       sort_keys=True,
                       indent=4)
        )
        self.tree_view.remove_node(self.tree_view.selected_node)

    def open_node_rightclick_menu(self, obj, touch):
        overlay = get_obj(self, 'Overlay')
        overlay.clear_menu()

        if touch.button == 'right' and self.collide_point(*touch.pos):
            overlay.open_menu(
                RightClickMenu(funcs=self.node_funcs,
                               pos=overlay.to_overlay_coord(touch,
                                                            self.tree_view.selected_node)
                               )
            )

        return True

    def get_node_names(self):
        node_names = []

        for node in self.tree_view.iterate_all_nodes():
            if type(node) != TreeViewLabel:
                node_names.append(node.text)

        return node_names

    def update_panel(self):
        c_label = None

        with open('nn_modules\\nn_nodes.json', 'r') as f:
            nodes = json.load(f)

            for node_name in nodes.keys():
                node_schematic = NodeSchematic()
                node_schematic.apply_schematic(nodes[node_name])

                if node_name not in self.get_node_names():
                    module = __import__('nn_modules.nn_components',
                                        fromlist=[node_name])
                    _class = getattr(module, node_name)
                    node = _class(tree_view=self.tree_view)
                    # print(node_name, node_schematic.attributes_get('node_type'))

                    if node_schematic.attributes_get('node_type') == FUNCTION:
                        c_label = self.function_nodes_label

                    elif node_schematic.attributes_get('node_type') == STACKED:
                        c_label = self.stacked_nodes_label

                    elif node_schematic.attributes_get('node_type') == NORM:
                        c_label = self.norm_nodes_label

                    self.tree_view.add_node(node, parent=c_label)


class SIToolBar(BoxLayout):
    def __init__(self, **kwargs):
        self.size_hint_y = 0.05
        self.size_hint_x = None
        # self.width = 400

        super(SIToolBar, self).__init__(**kwargs)


class IToolBar(TabbedPanel):
    _children = []


class Interface(StencilView, GridLayout, InterfaceSchematic):
    def __init__(self, **kwargs):
        super(Interface, self).__init__()
        self.size_hint = (1, 1)
        self.str_mapped_path = []
        self.hvfs = None
        self.model_name = 'Unknown'

        self.current_node_down = None
        self._node = None
        self._state = 0

        self.rows = 2
        self.cols = 3

        self.box_ori = (0, 0)

        # Selected Box Variables
        self.is_drawing_box = False
        self.enable_drawing_box = False

        self.is_trained = False
        self.is_drawing = False

        self.selected_box = []
        self.selected_nodes = []
        self.selected_beziers = []
        self.instructions = []

        self.selected_box_menu_button_height = 40
        self.selected_box_menu_button_width = 150
        self.selected_box_menu_spacing = 6

        self.connected_node_link = None

        self.rightclick_menu_funcs = {
            'Select Node(s)': lambda obj: setattr(self, 'enable_drawing_box', True)
        }

        self.selected_box_menu_funcs = {
            'Stacking Node(s)': self.grouping_nodes
        }

        self.action_bar_0 = SIToolBar(width=500)
        self.model_name_input = CustomTextInput(size_hint_x=0.3,
                                                max_length=50)
        self.model_name_input.bind(text=lambda obj, text: setattr(self,
                                                                  'model_name',
                                                                  text))

        self.action_bar_1 = SIToolBar(width=350)
        self.action_bar_2 = SIToolBar(width=350)
        self.scatter_plane = ScatterPlaneLayout()

        self.add_action_bar_2()
        self.add_action_bar_1()
        self.add_action_bar_0()

        self.add_widget(Widget())
        self.add_scatter_plane()

        self.nodes = self.allocating_nodes()
        self.node_links = self.allocating_node_links()

        self.bind(on_touch_up=self.add_node)

        Window.bind(mouse_pos=self._is_in_bbox)

        self.bind(on_touch_move=self.draw_link)
        self.bind(on_touch_move=self.draw_selected_box)
        self.bind(on_touch_move=self._update_canvas)

        self.bind(on_touch_down=self.touch_down)
        self.bind(on_touch_up=self.touch_up)

    # Last section of the action bar (index: 2)
    def add_action_bar_0(self):
        self.action_bar_0.add_widget(OpenGraphButton(interface=self))
        self.action_bar_0.add_widget(self.model_name_input)
        self.action_bar_0.add_widget(CheckpointButton(size_hint_x=0.2))
        self.action_bar_0.add_widget(TrainButton())

        self.add_widget(self.action_bar_0)

    # Second section of the action bar (index: 1)
    def add_action_bar_1(self):
        self.add_widget(self.action_bar_1)

    # First section of the action bar (index: 0)
    def add_action_bar_2(self):
        self.add_widget(self.action_bar_2)

    def add_scatter_plane(self):
        self.scatter_plane.do_rotation = False
        self.scatter_plane.do_scale = False
        self.scatter_plane.do_scroll = False
        self.scatter_plane.do_translation = False

        self.add_widget(self.scatter_plane)

    def check_nl_collision(self, touch):
        try:
            for node_link in self.node_links.values():
                if type(node_link) == NodeLink:
                    pos = node_link.to_widget(*touch.pos)

                    if node_link.collide_point(*pos):
                        return True, node_link.node, node_link

            return False, None, None

        except IndexError:
            pass

    # CAN BE OPTIMIZED
    def remove_rel(self, node_gate):
        targetNodeLink = self.node_links[node_gate.schema_get('target')]

        _rel = [f'{targetNodeLink.node.name} {targetNodeLink.name}',
                f'{node_gate.node.name} {node_gate.name}']

        self.cmap_get().remove(_rel)

    @staticmethod
    def unbind_connection(selected_node_link, target_node_link):
        selected_node_link.schema_set('connected', False)
        target_node_link.schema_set('connected', False)

        selected_node_link.schema_set('target', None)
        target_node_link.schema_set('target', None)

    def connection_exist(self):
        if self.touch_info_get('selected') and self.is_drawing and \
                self.node_links[self.touch_info_get('selected')].schema_get('target'):
            return True
        return False

    def get_bezier(self, begin: NodeLink, end:NodeLink):
        for widget in self.scatter_plane.children:
            if type(widget) == CustomBezier:
                if (widget.begin == begin and widget.end == end) or \
                        (widget.begin == end and widget.end == begin):
                    return widget

    def remove_bezier(self, bezier):
        node_link_begin = bezier.begin
        node_link_end = bezier.end

        self.unbind_connection(node_link_begin, node_link_end)

        self.instructions.remove(bezier)
        self.clear_canvas()

    def draw(self, ori=None, end=None, output_node=None, input_node=None):
        self.clear_canvas()
        midpoint0 = round((end[0] + ori[0]) / 2 + 20, 1)
        midpoint1 = round((end[0] + ori[0]) / 2 - 20, 1)

        bezier = CustomBezier(points=(ori[0], ori[1],
                                      midpoint0, ori[1],
                                      midpoint1, end[1],
                                      end[0], end[1]),
                              segments=800)

        if output_node and input_node:
            bezier.begin = self.node_links[output_node]
            bezier.end = self.node_links[input_node]

        self.scatter_plane.add_widget(bezier)
        return bezier

    def draw_link(self, obj, touch):
        if self.is_drawing:
            input_node = None
            output_node = self.touch_info_get('selected')

            if output_node:
                input_node = self.node_links[output_node].schema_get('target')

            self.draw(self.touch_info_get('down_pos'),
                      self.scatter_plane.to_local(*touch.pos),
                      output_node,
                      input_node)

    def touch_up(self, obj, touch):
        if touch.button == 'left' and self.collide_point(*touch.pos):
            try:
                valid, node, node_link = self.check_nl_collision(touch=touch)

                if valid:
                    if node_link.schema_get('gate_type') == 1 and not node_link.schema_get('connected'):
                        pos = node_link.get_center_position(self.scatter_plane)

                        selected_node_link = self.node_links[self.touch_info_get('selected')]

                        node_link.schema_set('target', self.touch_info_get('selected'))
                        bezier = self.draw(self.touch_info_get('down_pos'),
                                           pos,
                                           self.touch_info_get('selected'),
                                           f'{node.name} {node_link.name}')

                        self.beziers_coord_set([self.touch_info_get('down_pos'), pos])

                        self.cmap_set([self.touch_info_get('selected'),
                                       f'{node.name} {node_link.name}'])

                        selected_node_link.schema_set('target', f'{node.name} {node_link.name}')

                        node_link.schema_set('connected', True)
                        selected_node_link.schema_set('connected', True)
                        self.touch_info_set('selected', None)

                        self.instructions.append(bezier)
                        self.is_drawing = False

                    return True

                elif not valid:
                    if self.is_drawing:
                        self.is_drawing = False
                        self.clear_canvas()

                    if self.is_drawing_box:
                        overlay = get_obj(self, 'Overlay')
                        self.selected_box.append(self.scatter_plane.to_local(*touch.pos))
                        self.is_drawing_box = False
                        self.enable_drawing_box = False
                        self.select_nodes(overlay.to_local(*touch.pos))

                return False

            except Exception as e:
                raise e

    def touch_down(self, obj, touch):
        overlay = get_obj(self, 'Overlay')

        if touch.button == 'left' and self.collide_point(*touch.pos):
            overlay.clear_menu()
            self.clear_canvas()

            try:
                valid, node, node_link = self.check_nl_collision(touch=touch)

                if valid:
                    if node_link.schema_get('gate_type') == 0 and not node_link.schema_get('connected'):
                        pos = node_link.get_center_position(self.scatter_plane)

                        self.touch_info_set('down_pos', pos)
                        self.touch_info_set('selected', f'{node_link.node.name} {node_link.name}')
                        self.is_drawing = 1

                    elif node_link.schema_get('gate_type') == 1 and node_link.schema_get('connected'):
                        self.touch_info_set('selected', f'{node_link.node.name} {node_link.name}')

                    return True

                elif not valid and self.enable_drawing_box:
                    # Touching the interface's canvas
                    if self.collide_point(*touch.pos):
                        self.box_ori = self.scatter_plane.to_local(*touch.pos)
                        self.is_drawing_box = True
                        self.selected_box.append(self.box_ori)

                    return True

                return False

            except Exception as e:
                raise e

        elif touch.button == 'right':
            if self.collide_point(*touch.pos):
                menu = RightClickMenu(pos=overlay.to_overlay_coord(touch, self),
                                      button_width=140,
                                      funcs=self.rightclick_menu_funcs)
                overlay.open_menu(menu)

            else:
                overlay.clear_menu()

    def add_selected_box_menu(self, top_right_overlay):
        if self.selected_nodes:
            # Default `selected_box_menu`'s Button height is 30 unit and width is 120 unit
            x = top_right_overlay[0]
            y = top_right_overlay[1]
            funcs = self.selected_box_menu_funcs

            overlay = get_obj(self, 'Overlay')

            menu_layout_height = \
                self.selected_box_menu_button_height * \
                len(funcs.keys()) + \
                self.selected_box_menu_spacing * (len(funcs.keys()) - 1)

            menu_layout = BoxLayout(size_hint=(None, None),
                                    size=(self.selected_box_menu_button_width,
                                          menu_layout_height),
                                    pos=(x, y - menu_layout_height),
                                    orientation='vertical',
                                    spacing=self.selected_box_menu_spacing)

            for func_name in funcs.keys():
                button = Button(text=func_name,
                                size_hint=(None, None),
                                size=(self.selected_box_menu_button_width,
                                      self.selected_box_menu_button_height))
                button.bind(on_press=lambda obj: funcs[func_name]())
                menu_layout.add_widget(button)
            overlay.open_menu(menu_layout)
        else:
            # Clear Canvas if there aren't any nodes selected
            self.clear_canvas()

    def group_infos(self):
        input_nodes = []
        output_nodes = []

        for node in self.selected_nodes:
            if 'Input' in node.layer_get():
                input_nodes.append(node)

            elif 'Output' in node.layer_get():
                output_nodes.append(node)

        return input_nodes, output_nodes

    # Checking if all the selected nodes is an independent group
    @staticmethod
    def is_independent_group(input_nodes, output_nodes):
        n_inputs = 0
        n_outputs = 0

        for input_node in input_nodes:
            for children in input_node.children[0].children:
                if type(children) == NodeLink and children.schema_get('gate_type') == 1:
                    if not children.schema_get('target'):
                        n_inputs += 1
                        break

        for output_node in output_nodes:
            for children in output_node.children[0].children:
                if type(children) == NodeLink and children.schema_get('gate_type') == 0:
                    if not children.schema_get('target'):
                        n_outputs += 1
                        break

        if n_inputs + n_outputs == len(input_nodes) + len(output_nodes):
            return True
        return False

    # Set nodes name
    def set_nodes_name(self, node, template, currentNodeName):
        def remove_old_nodes(obj, _node, _template, _currentNodeName):
            for node in obj.selected_nodes:
                for hierarchy_node in hierarchy.iterate_all_nodes():
                    if node.name == hierarchy_node.text:
                        hierarchy.add_node(TreeViewLabel(text=node.name),
                                           parent=parent_node)
                        hierarchy.remove_node(hierarchy_node)
                        break

            _template['model'][_node.name] = template['model'].pop(_currentNodeName)

        hierarchy = get_obj(self, 'Hierarchy')

        parent_node = TreeViewLabel(text='Parent Node')
        parent_node.bind(on_touch_down=hierarchy.open_rightclick_menu)
        hierarchy.add_node(parent_node)

        nodesNamePopup = GroupNamePopup(parent_node=parent_node,
                                        func=remove_old_nodes,
                                        node=node,
                                        obj=self,
                                        hierarchy=hierarchy,
                                        template=template,
                                        currentNodeName=currentNodeName)
        nodesNamePopup.open()

        # node_label.text = parent_node.text

    # Group all `selected_nodes` into one stacked node
    # Manually set Input and Output Node for selected nodes
    # Throw warning when there is any unconnected node
    def grouping_nodes(self):
        overlay = get_obj(self, 'Overlay')
        hierarchy = get_obj(self, 'Hierarchy')
        input_nodes, output_nodes = self.group_infos()

        if input_nodes and output_nodes and self.is_independent_group(input_nodes, output_nodes) and \
                len(self.selected_beziers) >= len(self.selected_nodes) - 1:

            spawn_position = [0, 0]
            for node in self.selected_nodes:
                spawn_position[0] += node.pos[0]
                spawn_position[1] += node.pos[1]

            spawn_position[1] /= len(self.selected_nodes)
            spawn_position[0] /= len(self.selected_nodes)

            schematic = {
                "attributes": {
                    "layer": "Hidden Layer",
                    'nl_output': {
                        'n_links': len(output_nodes),
                        'position': RIGHT_CODE,
                        'type': 'output'
                    },
                    'nl_input': {
                        'n_links': len(input_nodes),
                        'position': LEFT_CODE,
                        'type': 'input'
                    },
                    "node_class": "Stacked",
                    "node_type": STACKED
                },
                "node_links": {
                    "input": [],
                    "output": []
                },
                "cmap": [],
                "graphic_attributes": {
                    "beziers_coord": [],
                    "node_pos": [
                        0,
                        0
                    ]
                },
                "properties": {},
                "script": "i_modules/stacked_code_template.py",
                "sub_nodes": {}
            }

            for selected_node in self.selected_nodes:
                schematic['sub_nodes'].update({selected_node.name: selected_node})

            for bezier in self.selected_beziers:
                nodes_relationship = [
                    f'{bezier.begin.node.name} {bezier.begin.name}',
                    f'{bezier.end.node.name} {bezier.end.name}'
                ]

                beziers_coord = get_bezier_endpoints(bezier)

                schematic['cmap'].append(nodes_relationship)
                self.schema['cmap'].remove(nodes_relationship)

                schematic['graphic_attributes']['beziers_coord'].append([beziers_coord])
                self.schema['beziers_coord'].remove(beziers_coord)
                self.instructions.remove(bezier)

            self._node = Node
            self._node.algorithm = stacked_algorithm
            self.add_node2interface(schematic=schematic,
                                    node_name='Stacked',
                                    spawn_position=spawn_position)

            # Clear grouped nodes
            for node in self.selected_nodes:
                self.remove_node(node)

            # Clean canvas after rendering new grouped node
            overlay.clear_menu()

            # Somehow you have to invoke `self.clear_canvas()`
            # twice to get rid of the selection box
            self.clear_canvas()
            self.clear_canvas()
        else:
            print(f'[DEBUG]: Warning: There is no Output / Input Layer (And the number of'
                  f' links must be at least: {len(self.selected_nodes) - 1})')

    # Create a virtual box for referencing the position of the nodes
    @staticmethod
    def get_virtual_box(rpos0, rpos1):
        left, right, top, bottom = None, None, None, None

        # Determine left & right coord of the box
        if rpos0[0] < rpos1[0]:
            left = rpos0[0]
            right = rpos1[0]

        elif rpos0[0] > rpos1[0]:
            left = rpos1[0]
            right = rpos0[0]

        # Determine top & bottom coord of the box
        if rpos0[1] < rpos1[1]:
            top = rpos1[1]
            bottom = rpos0[1]

        elif rpos0[1] > rpos1[1]:
            top = rpos0[1]
            bottom = rpos1[1]

        return left, right, top, bottom

    # Check if object's position is in referenced range
    # `rpos0` and `rpos1` are the references of first position and second position
    def is_in_range(self, pos, rpos0, rpos1):
        left, right, top, bottom = self.get_virtual_box(rpos0, rpos1)

        if (left <= pos[0] <= right) and (bottom <= pos[1] <= top):
            return True

    def select_nodes(self, top_right_overlay):
        # Clear selected elements before invoke any actions
        self.selected_nodes.clear()
        self.selected_beziers.clear()

        bottom_left = self.selected_box[0]
        top_right = self.selected_box[1]

        for node_name in self.nodes.keys():
            if self.is_in_range(self.nodes[node_name].pos, bottom_left, top_right):
                self.selected_nodes.append(self.nodes[node_name])

        for ins in self.scatter_plane.canvas.children:
            if type(ins) == CustomBezier:
                bezier_pos_bottom_left = ins.points[:2]
                bezier_pos_top_right = ins.points[-2:]

                if self.is_in_range(bezier_pos_bottom_left, bottom_left, top_right) and \
                        self.is_in_range(bezier_pos_top_right, bottom_left, top_right):
                    self.selected_beziers.append(ins)

        self.add_selected_box_menu(top_right_overlay)

    def _draw_selected_box(self, ori=None, end=None):
        self.clear_canvas()
        self.scatter_plane.canvas.ask_update()

        with self.scatter_plane.canvas:
            Line(
                points=(ori[0], ori[1],
                        end[0], ori[1],
                        end[0], end[1],
                        ori[0], end[1],
                        ori[0], ori[1])
            )

    def draw_selected_box(self, obj, touch):
        if self.is_drawing_box and self.box_ori != (0, 0):
            self._draw_selected_box(self.box_ori,
                                    self.scatter_plane.to_local(*touch.pos))

    def remove_node(self, node):
        self.scatter_plane.remove_widget(node)
        self.nodes.pop(node.name)

    def _is_in_bbox(self, obj, pos):
        _pos = self.to_widget(*pos)

        if self.collide_point(*_pos) and not self.action_bar_0.collide_point(*_pos):
            self.scatter_plane.do_translation = True
        else:
            self.scatter_plane.do_translation = False

        return True

    def num_nodes(self, node_class):
        c = 0

        for node in self.nodes.keys():
            if node_class in node:
                c += 1

        return c

    def allocating_node_links(self):
        node_links = {}

        for node_name in self.nodes.keys():
            for node_link in self.nodes[node_name].inputs:
                node_links.update({f'{node_name} {node_link.name}': node_link})

            for node_link in self.nodes[node_name].outputs:
                node_links.update({f'{node_name} {node_link.name}': node_link})

            # for widget in node.children[0].children:
            #     if type(widget) == NodeLink:
            #         node_links.update({f'{node.name} {widget.name}': widget})

        return node_links

    def allocating_nodes(self):
        nodes = {}

        for widget in get_obj(self, 'ScatterPlaneLayout').children:
            if 'Node' in str(widget):
                nodes.update({widget.name: widget})

        return nodes

    def add_node2interface(self, schematic=None, node_name=None, spawn_position=(0, 0), has_parent=False):
        with open('nn_modules\\nn_nodes.json', 'r') as f:
            nodes = json.load(f)

            if not node_name:
                node_class = str(self._node).split('.')[-1].split('Node')[0]
                node_name = f'{node_class} {self.num_nodes(node_class)}'

            if not schematic:
                schematic = nodes[node_class]

            node = self._node(spawn_position=spawn_position,
                              interface=self,
                              schematic=schematic,
                              node_name=node_name)

            node.node_pos_set(spawn_position)
            self.nodes.update({node_name: node})

            get_obj(self, 'ScatterPlaneLayout').add_widget(node)
            self._state = 0
            self._node = None

            try:
                hierarchy = get_obj(self, 'Hierarchy')
                hierarchy.load_hierarchy_from_interface(self)
            except AttributeError:
                pass

            return node

    def add_node(self, obj, touch):
        if touch.button == 'left' and self.collide_point(*touch.pos):
            if self._state == 1:
                spl = get_obj(self, 'ScatterPlaneLayout')
                pos = spl.to_local(*touch.pos)

                self.add_node2interface(spawn_position=pos)
                # self.create_template(node)

            return True

    def add_node_names(self, hierarchy, node_class=None, has_parent=False):
        # if not node_name:
        # node_class = node_class.split(' ')[0]
        # node_class = node_class.split('.')[-1]
        # node_class = node_class[0:-4]
        node_name = f'{node_class} {self.num_nodes(node_class)}'

        # self.node_names.append(node_name)

        # node_name_obj = get_obj(node, 'NodeName')
        # node_name_obj.text = node.name = node_name

        if not has_parent:
            hierarchy.add_tree_node(node_name)

        return node_name

    def clear_canvas(self):
        for widget in self.scatter_plane.children:
            if widget not in self.instructions and type(widget) == CustomBezier:
                self.scatter_plane.remove_widget(widget)

    def _update_canvas(self, obj, touch):
        try:
            self.clear_canvas()

            if self.collide_point(*self.to_widget(*obj.pos)) \
                    and len(self.instructions) >= 1 \
                    and not self.is_drawing \
                    and touch.button == 'left':
                # for node_link_name in self.node_links.keys():
                #     node_link = self.node_links[node_link_name]
                #
                #     if node_link.schema_get('target'):
                #         target_node_link = self.node_links[node_link.schema_get('target')]
                #         # print(target_node_link.pos)

                for bezier in self.instructions:
                    node_link = bezier.begin
                    target_node_link = bezier.end

                    # if bezier.begin == node_link:
                    # ori = node_link.to_scatter_plane(self.scatter_plane)
                    # end = target_node_link.to_scatter_plane(self.scatter_plane)
                    # ori = node_link.schema_get('c_pos')
                    # end = target_node_link.schema_get('c_pos')

                    points = bezier.points
                    old_bezier_coord = [
                        [points[0], points[1]],
                        [points[-2], points[-1]]
                    ]

                    # ori = list(node_link.to_scatter_plane(self.scatter_plane))
                    # ori[0] += node_link.width / 2
                    # ori[1] += node_link.height / 2
                    # ori = round_pos(ori)

                    # end = list(target_node_link.to_scatter_plane(self.scatter_plane))
                    # end[0] += target_node_link.width / 2
                    # end[1] += target_node_link.height / 2
                    # end = round_pos(end)

                    ori = node_link.get_center_position(self.scatter_plane)
                    end = target_node_link.get_center_position(self.scatter_plane)

                    midpoint0 = round((end[0] + ori[0]) / 2 - 20, 1)
                    midpoint1 = round((end[0] + ori[0]) / 2 + 20, 1)

                    bezier.points = (ori[0], ori[1],
                                     midpoint0, ori[1],
                                     midpoint1, end[1],
                                     end[0], end[1])

                    index = self.schema['beziers_coord'].index(old_bezier_coord)
                    self.schema['beziers_coord'][index] = [ori, end]

                    # node_link.schema_set('c_pos', ori)
                    # node_link.schema_set('target_pos', end)
                    #
                    # target_node_link.schema_set('c_pos', end)
                    # target_node_link.schema_set('target_pos', ori)
        except IndexError:
            pass

    def create_template(self, node=None):
        node_properties = {}
        node_properties.update(node.properties)

        for obj in node.sub_layout.children:
            if type(obj) == Spinner:
                obj_name = obj.text

                if 'Layer' in obj_name:
                    node_properties.update({'Layer': [LAYER_CODE, obj.text]})

        self.template['model'].update({node.name: {'properties': node_properties}})

        # if node.attributes_get('node_type') != STACKED:
        # node.attributes_set('node_class', node.node_class)
        # self.template['model'][node.name].update({'node_class': node.node_class})

    def get_hvfs(self):
        hvfs = get_obj(self, 'IToolBar')
        hvfs_properties = {}

        for tab in hvfs.tab_list:
            # print(tab.text)
            # print(tab.content)
            current_func = tab.content.children[1].text
            hvfs_properties.update({tab.text: {current_func: {}}})

            for obj in tab.content.children:
                if type(obj) == GridLayout:
                    for children in obj.children:
                        hvfs_properties[tab.text][current_func].update({children.name: str(children.value)})

        return hvfs_properties

    def __dict__(self):
        nodes_key = self.schema['nodes'].keys()

        for node in nodes_key:
            node_schema = self.schema['nodes'][node].schema
            node_links = node_schema['node_links']

            for io in ['input', 'output']:
                # print(len(node_links[io]))
                for nl_index in range(len(node_links[io])):
                    # print(node_links[io][nl_index].schema)
                    node_link_io_schema = node_links[io][nl_index].schema
                    target_node_link = node_link_io_schema['target']

                    if target_node_link:
                        target_node = target_node_link.schema['node']
                        node_links[io][nl_index].schema['target'] = f'{target_node.name} {target_node_link.name}'

        for node in nodes_key:
            node_schema = self.schema['nodes'][node].schema
            node_links = node_schema['node_links']

            for io in ['input', 'output']:
                for nl_index in range(len(node_links[io])):
                    node_links[io][nl_index].schema.pop('node')
                    self.schema['nodes'][node].schema['node_links'][io][nl_index] = node_links[io][nl_index].schema

        for node in nodes_key:
            self.schema['nodes'][node] = self.schema['nodes'][node].schema

        self.schema['hvfs'] = self.get_hvfs()

        return self.schema


class ILayout(BoxLayout):
    def __init__(self, **kwargs):
        super(ILayout, self).__init__()
        self.orientation = 'vertical'

        self.add_widget(Interface())
        self.scatter_plane = self.children[-1].scatter_plane

        self.bind(on_touch_down=self.mouse_scrolled)

    # For zooming in and out of the Interface
    def mouse_scrolled(self, obj, touch):
        if self.collide_point(*touch.pos):
            if touch.is_mouse_scrolling:
                if touch.button == 'scrolldown':
                    if self.scatter_plane.scale <= 1.0:
                        self.scatter_plane.scale *= 1.1
                        # print('zoom out')

                elif touch.button == 'scrollup':
                    if self.scatter_plane.scale > 0.3:
                        # print('zoom in')
                        self.scatter_plane.scale *= 0.8
                # print(self.scatter_plane.scale)


class SubContainer1(BoxLayout):
    def __init__(self, **kwargs):
        super(SubContainer1, self).__init__()
        self.orientation = 'vertical'
        self.spacing = 5
        self.size_hint = (0.8, 1)
        self.state = 0

        self.sub_layout = SubLayout(size_hint_y=0.035,
                                    padding=[10, 0, 10, 0])

        self.sub_layout.add_widget(Label(size_hint_x=0.3))
        self.sub_layout.add_widget(TrainedModelLabel(size_hint_x=0.1))
        self.sub_layout.add_widget(ProgressIndicator(size_hint_x=0.1))
        self.sub_layout.add_widget(ModeLabel(size_hint_x=0.1))
        self.sub_layout.add_widget(ProgressBar(size_hint_x=0.4,
                                               max=100))

        self.tab_manager = InterfaceTabManager(func=ILayout,
                                               default_name='New Model',
                                               _fkwargs={})
        self.add_widget(self.tab_manager)
        self.add_widget(self.sub_layout)

    def _open_dropdown(self, obj):
        overlay = get_obj(self, '_container').request_obj('Overlay')

        if self.state == 0:
            for i, key in enumerate(sorted(self.button_dict.keys())):
                button = Button(size_hint=(0.14, 0.0485),
                                pos=(obj.pos[0] - obj.width * 4.5,
                                     obj.pos[1] + i * 36),
                                text=key
                                )
                button.bind(on_press=self.button_dict[key])
                overlay.add_widget(button)

            self.state = 1

        elif self.state == 1:
            for children in overlay.children:
                if type(children) == Button:
                    overlay.remove_widget(children)

            self.state = 0

        return True

    def add_new_model(self, obj):
        self.tab_manager.add_tab(func_name='New Model',
                                 _fkwargs={})


class SubContainer2(BoxLayout):
    def __init__(self, **kwargs):
        super(SubContainer2, self).__init__()
        self.orientation = 'vertical'
        self.spacing = 10
        self.size_hint = (0.2, 1)

        self.sub_layout = BoxLayout(spacing=5,
                                    orientation='vertical',
                                    size_hint_y=0.5)

        # Update initial BaseInputForm for every BaseForms
        self.interface_toolbar = IToolBar()
        self.hierarchy = Hierarchy(hide_root=True)

        self.add_widget(self.sub_layout)
        self.add_widget(self.interface_toolbar)
        self.sub_layout.add_widget(self.hierarchy)

        # self.sub_layout.add_widget(ComponentPanel())


class Container(BoxLayout, Widget):
    def __init__(self, **kwargs):
        super(Container, self).__init__()
        self.orientation = 'vertical'
        self.spacing = 10

        self.main_sub_layout = BoxLayout(orientation='vertical',
                                         spacing=10)

        self.sub_layout = BoxLayout(orientation='horizontal',
                                    spacing=10,
                                    padding=10)

        # Change ComponentPanel to left-side of the Interface
        self.sub_layout.add_widget(ComponentPanel())
        self.sub_layout.add_widget(SubContainer1())
        self.sub_layout.add_widget(SubContainer2())

        component_panel = get_obj(get_obj(self.sub_layout, 'SubContainer2').children[1], 'ComponentPanel')
        self.tool_bar = CustomActionBar(component_panel=component_panel)

        self.main_sub_layout.add_widget(self.tool_bar)
        self.main_sub_layout.add_widget(self.sub_layout)

        self.add_widget(self.main_sub_layout)
