from matplotlib import mathtext
import matplotlib as mpl
import matplotlib.pyplot as plt
import os
import re
from datetime import datetime

def print_fig_to_paper(output_type, plot_file_name, fig_font_size=16, fig_font_name='Times New Roman', fig_width=7, 
                       is_print=True, is_print_time=True, fig=None, fig_height_custom=None, is_hide_axis=False, output_path=None):
    '''
    Adjust the format of the figure to be suitable for the journal paper.
    output_type options in matplotlib: 'eps', 'pdf', 'png'
    fig_font_size: font size  ## NOTE: 50% insert into lyx, then the fontsize in the journal paper will be 8pt, close to the fontsize of the text in the journal paper
    fig_font_name: the name of the font
    fig_width: Width of the figure
    is_print: Whether to save the figure
    is_print_time: Whether to add the current time to the file name
    fig: The figure to be saved, if None, the current figure (plt.gcf()) will be saved
    figu_height_custom: Custom height of the figure
    is_hide_axis: Whether to hide the axis
    '''
    numdip = 300

    fig = fig or plt.gcf()
    
    # Set font properties
    # plt.rcParams.update({'font.size': fig_font_size, 'font.family': fig_font_name})
    
    # Use xelatex to render the text, including the mathemtical symbols
    # plt.rcParams['text.usetex'] = True
    # plt.rcParams['pgf.texsystem'] = 'xelatex'
    # plt.rcParams['pgf.rcfonts'] = False
    # plt.rcParams['pgf.preamble'] = '\n'.join([
    #     r'\usepackage{fontspec}',
    #     r'\setmainfont{Times New Roman}'])
    # mpl.use("pgf")
    
    # set the default font of mathtext to fig_font_name
    plt.rcParams['mathtext.fontset'] = 'custom'
    plt.rcParams['mathtext.it'] = fig_font_name + ':italic'
    plt.rcParams['mathtext.bf'] = fig_font_name + ':bold'
    plt.rcParams['mathtext.rm'] = fig_font_name
    plt.rcParams['mathtext.sf'] = fig_font_name
    
    # Get current figure dimensions
    current_fig_width, current_fig_height = fig.get_size_inches()
    
    # Calculate figure height maintaining the aspect ratio
    fig_height = fig_width / current_fig_width * current_fig_height
    
    # If custom height is specified
    fig_height = fig_height_custom or fig_height
    
    # Set figure size
    fig.set_size_inches(fig_width, fig_height)
    
    if is_hide_axis:
        ax = plt.gca()
        ax.xaxis.set_visible(False)
        ax.yaxis.set_visible(False)
    else:
        ax = plt.gca()
        ax.set_facecolor('none') # clear the background color of the axis
    
    for text in fig.findobj(match=plt.Text):
        # set the size and font of the text, specify custom math font
        text.set_fontsize(fig_font_size)
        text.set_fontname(fig_font_name)
        text.set_math_fontfamily('custom')
        text.set_fontfamily(fig_font_name)
        # if pattern.search(text.get_text()): # if the text contains math symbols
        #     text.set_usetex(True)

    fig.tight_layout()
    
    # Ensure the 'pic' directory exists
    if not output_path and not os.path.exists('pic'):
        os.makedirs('pic')
        output_path = 'pic'

    # Save the figure
    if is_print:
        if is_print_time:
            plot_file_name = f"{output_path}/{plot_file_name}{datetime.now().strftime('%Y%m%dT%H%M%S')}.{output_type}"
        else:
            plot_file_name = f"{output_path}/{plot_file_name}.{output_type}"

        fig.savefig(plot_file_name, format=output_type, dpi=numdip, bbox_inches='tight')

# Example usage
if __name__ == "__main__":
    import numpy as np
    
    # Example plot
    x = np.linspace(0, 10, 100)
    y = np.sin(x)
    plt.plot(x, y)
    
    # Call the function with your parameters
    print_fig_to_paper(output_type='png', plot_file_name='example_plot', 
                       fig_font_size=16, fig_font_name='Times New Roman', 
                       fig_width=7, is_print=True, is_print_time=True)

