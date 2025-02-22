import copy
import json
import kivy

from os.path import abspath
from kivy.uix.spinner import Spinner

from nn_modules.node_link import NodeLink
from nn_modules.node_utils import CustomValueInput, CustomSpinnerInput
from schematics.node_schematic import NodeSchematic
from utility.utils import get_obj, draw_beziers, formatting_rels, remove_node_from_interface
from nn_modules.code_names import *
from nn_modules.node_graphic import NodeGraphic

kivy.require('2.0.0')


class Node(NodeGraphic, NodeSchematic):
    def __init__(self, schematic=None, interface=None, **kwargs):
        super(Node, self).__init__(**kwargs)
        self.is_loaded = False
        self.apply_schematic(schematic)

        # self.properties = kwargs.get('properties')
        # self.properties = {}

        self.inputs = []
        self.outputs = []

        self.code_names = [INT_CODE, STR_CODE, FLOAT_CODE, OBJ_CODE]

        self.interface = interface
        # self.interface_template = type(self.interface)()
        self.add_components()
        self.add_ib()

        self.stacked_funcs = {
            'De-grouping Node(s)': self.degrouping_nodes
        }

        self.norm_funcs = {
            'Remove Node': self.delete_node
        }

        # Combining components and add event listener/handler
        self.combine()
        self.bind(on_touch_down=self.open_rightclick_menu)

    # In the future version `node_link` will be changed to `node_gate` or `gate`
    def node_links(self):
        node_links = []

        for children in self.children[0].children:
            if type(children) == NodeLink:
                node_links.append(children)

        return node_links

    def is_connected(self):
        c = 0
        node_links = copy.copy(self.outputs)
        node_links.extend(self.inputs)

        for node_link in node_links:
            if not node_link.target:
                c += 1

        if c == len(self.outputs) + len(self.inputs):
            return True
        return False

    @staticmethod
    def get_degrouped_node_class(node_class):
        module = __import__('nn_modules.nn_nodes',
                            fromlist=[node_class + 'Node'])
        return getattr(module, node_class + 'Node')

    # FIX
    def degrouping_nodes(self, obj):
        if self.type == STACKED and self.is_connected():
            with open('./nn_modules/nn_nodes.json', 'r') as f:
                node_templates = json.load(f)

                # REMOVE STACKED NODE'S NAME AND UPDATE THE HIERARCHY
                self.remove_node_from_hierarchy(self.name)

                for node_name in self.properties.keys():
                    try:
                        node_class = self.properties[node_name]['node_class']

                        # Node's template format
                        template = {
                            'pos': self.properties[node_name]['pos'],
                            'properties': {
                                'nl_input': node_templates[node_class]['nl_input'],
                                'nl_output': node_templates[node_class]['nl_output'],
                                'node_type': NORM,
                                'Layer': self.properties[node_name]['properties']['Layer']
                            }
                        }

                        for property_name in self.properties[node_name]['properties']:
                            template['properties'].update({
                                property_name: self.properties[node_name]['properties'][property_name]
                            })

                        # Initialize Node's properties
                        node = self.get_degrouped_node_class(node_class)
                        node.node_template = template['properties']
                        node.type = NORM
                        node.node_class = node_class
                        node.algorithm = self.get_algorithm(node_class)
                        node.name = node_name

                        self.interface._node = node
                        self.interface.template['model'].update({node_name: template})

                        node = self.interface.add_node2interface(
                            node_name=node_name,
                            spawn_position=self.properties[node_name]['pos']
                        )

                        node.c_type = \
                            node.dropDownList.text = \
                            self.properties[node_name]['properties']['Layer'][1]

                    except TypeError:
                        pass
                        # if 'Layer' in node_name:
                        #     self.set_type(None, self.properties['Layer'][1])

                draw_beziers(self.node_template,
                             self.interface)

                self.interface.remove_node(self)
        else:
            print('[DEBUG]: Node is being connected to other Node(s). '
                  'Please disconnected them before de-grouping')

    def num_nl(self, nl_type=1):
        count = 0

        for children in self.children:
            if type(children) == NodeLink and children.c_type == nl_type:
                count += 1

        return count

    def remove_node_from_hierarchy(self, node_name):
        hierarchy = get_obj(self.interface, 'Hierarchy')
        for hierarchy_node in hierarchy.iterate_all_nodes():
            if hierarchy_node.text == node_name:
                hierarchy.remove_node(hierarchy_node)
                break

    def delete_node(self, obj):
        self.remove_node_from_hierarchy(self.name)
        remove_node_from_interface(self.interface, self.name)

    # Placeholder function for the algorithm of family of Nodes
    def algorithm(self):
        pass

    @staticmethod
    def get_functions(node_name):
        module = __import__('nn_modules.nn_nodes',
                            fromlist=[node_name + 'Node'])
        _class = getattr(module, node_name + 'Node')

        return _class

    # Split `Stacked Node` properties to separate child's properties
    def set_nodes_properties(self, node_obj, properties):
        for widget in node_obj.sub_layout.children:
            if type(widget) == CustomValueInput or type(widget) == CustomSpinnerInput:
                variable = self.properties[node_obj.name]['properties'][widget.label.text]

                node_obj.properties[widget.label.text][1] = str(variable[1])
                node_obj.properties[widget.label.text][0] = variable[0]

    def set_model_properties(self, model):
        for key in model.keys():
            if key != 'rels' and key != 'beziers_coord':
                try:
                    self.attributes_set('node_type', key.split(' ')[0])
                    node = self.get_functions(self.attributes_get('node_type'))

                    self.interface_template._node = node
                    node = self.interface_template.add_node2interface(node_name=key,
                                                                      has_parent=True)

                    for widget in node.sub_layout.children:
                        if type(widget) == Spinner:
                            node.c_type = self.properties[node.name]['properties']['Layer'][1]

                    self.set_nodes_properties(node_obj=node,
                                              properties=self.properties[key]['properties'])

                except AttributeError as e:
                    raise e

    def load_nodes(self):
        if not self.is_loaded:
            # print(f'Load Nodes: {self.interface_template.nodes()}')
            model = None
            datas = None

            try:
                with open(abspath('models/' + self.name.split(' ')[0] + '.json'), 'r') as f:
                    datas = json.load(f)
                    model = datas['model']
            except FileNotFoundError:
                pass

            if model and datas:
                self.set_model_properties(model)
                self.binding(datas=datas)
            else:
                # print(self.node_template)
                self.set_model_properties(self.node_template['model'])
                self.binding(datas=self.node_template)

            self.is_loaded = True
            # print(self.interface_template.nodes())

    def binding(self, datas=None):
        rels = formatting_rels(datas['rels'], self.interface_template.node_links())

        for rel in rels:
            rel[1].target = rel[0]

            rel[0].target = rel[1]
            nl_index = rel[0].index()
            node_name = rel[0].node.name

            rel[0].connected = 1
            rel[1].connected = 1
