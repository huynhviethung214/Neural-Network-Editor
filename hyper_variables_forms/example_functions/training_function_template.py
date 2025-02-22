import torch
import numpy as np
from utility.utils import record_graph, checkpoint


@checkpoint
@record_graph
def training_alg(self, properties):
    # Create `losses` variable as an array for plotting graph after training
    losses = []
    # Your code goes here
    # Add `breaker(self)` in loop that you want to break

    # Use this line of code to update ProgressBar value, remember to put it inside
    # the epoch's loop
    # update_progress_bar(properties['interface'],
    #                    epoch + 1,
    #                    properties['epochs'])

    properties['obj']._evaluate(properties['eval_properties'],
                                properties['eval_properties']['eval_code'])

    if properties['is_save']:
        # Uncomment and remove `pass` to save model's output
        # torch.save(properties['model'].state_dict(), '{0}.prmt'.format(properties['output_file_name']))
        # torch.cuda.empty_cache()
        pass

    return losses, properties['epochs']
