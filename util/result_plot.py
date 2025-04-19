import matplotlib.pyplot as plt
from matplotlib import rcParams
from matplotlib import style
from matplotlib.lines import Line2D
import os
import numpy as np
from datetime import datetime

plt.rcParams["font.family"] = "Times new Roman"
plt.rcParams['mathtext.fontset'] = 'custom'
plt.rcParams['mathtext.rm'] = 'Times New Roman'
plt.rcParams['mathtext.it'] = 'Times New Roman:italic'
plt.rcParams['mathtext.bf'] = 'Times New Roman:bold'

def print_fig_to_paper(output_type, plot_file_name, fig_font_size=16, fig_font_name='Times New Roman', fig_width=7, 
                       is_print=True, is_print_time=True, fig=None, fig_height_custom=None, is_hide_axis=False):
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
        # if pattern.search(text.get_text()): # if the text contains math symbols
        #     text.set_usetex(True)

    fig.tight_layout()
    
    # Ensure the 'pic' directory exists
    if not os.path.exists('pics'):
        os.makedirs('pics')

    # Save the figure
    if is_print:
        if is_print_time:
            plot_file_name = f"pics/{plot_file_name}{datetime.now().strftime('%Y%m%dT%H%M%S')}.{output_type}"
        else:
            plot_file_name = f"pics/{plot_file_name}.{output_type}"
        
        fig.savefig(plot_file_name, format=output_type, dpi=numdip, bbox_inches='tight')

cmap = plt.get_cmap('tab10')
colors = cmap(np.linspace(0, 1, 10))  # Extract 20 colors

#The relationship between fork rate/stale rate and maximum propagation delay
x=[1, 5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
y2=[0.02384, 0.08232, 0.12278, 0.17116, 0.20658, 0.22953, 0.25170, 0.26720, 0.28061, 0.29478, 0.30891, 0.32458]
y3=[0.02388, 0.08314, 0.12603, 0.17861, 0.21518, 0.24189, 0.26576, 0.28254, 0.30007, 0.31203, 0.32683, 0.34365]
plt.rcParams["font.family"] = "Times new Roman"
plt.grid(True, linestyle='--', linewidth=0.5, color='Grey')
plt.plot(x, y2, color=colors[0],marker='^',markerfacecolor='none',markeredgewidth=1, markersize=10,linestyle='--',label='Stale rate')
plt.plot(x, y3, color=colors[1],marker='s',markerfacecolor='none',markeredgewidth=1, markersize=10,linestyle='--',label='Fork rate')
plt.legend(loc="upper left", prop={"size": 15})
plt.xlabel('Maximum propagation delay (Round)',fontsize = 17)
plt.ylabel('Stale rate and Fork rate',fontsize = 17)
plt.ylim([0,0.40])
plt.xlim([0, 101])
print_fig_to_paper(output_type='png', plot_file_name='latency-fork', 
                    fig_font_size=16, fig_font_name='Times New Roman', 
                    fig_width=7, is_print=True, is_print_time=False)
plt.show()

#The relationship between consistency indicators and maximum propagation delay
x1=[1, 20, 40, 60, 80, 100]
z=[0.97508, 0.63863, 0.52804, 0.45583, 0.40939, 0.36903]
u1=[0.97508, 0.63863, 0.52804, 0.45583, 0.40939, 0.36903]
u2=[0.02441, 0.31348, 0.38345, 0.42242, 0.43670, 0.45102]
u3=[0.00047, 0.04423, 0.07793, 0.10499, 0.12885, 0.14852]
u4 = [x+y for x,y in zip(u1,u2)]
u5 = [x+y+z for x,y,z in zip(u1,u2,u3)]
plt.grid(True, linestyle='--', linewidth=0.5, color='Grey')
plt.bar(x=x1, height=[1, 1, 1, 1, 1, 1], edgecolor='#2A2A2A', linewidth=1, label='Others', width=10, color='#FFF0C8', alpha=1.0)
plt.bar(x=x1, height=u5, width=10, edgecolor='#2A2A2A', linewidth=1, label='Common Prefix [2]', color='#FFDCA0', alpha=1.0)
plt.bar(x=x1, height=u4, width=10, edgecolor='#2A2A2A', linewidth=1, label='Common Prefix [1]', color='#FFBB78', alpha=0.7)
plt.bar(x=x1, height=u1, width=10, edgecolor='#2A2A2A', linewidth=1, label='Common Prefix [0]', color='#FF9E4A', alpha=0.6)
plt.plot(x1, z, marker='.', color='#D62728', linewidth='2')
plt.ylim([0, 1])
plt.legend(loc="lower left", prop={"size": 15})
plt.xlabel("Maximum propagation delay (Round)", fontsize = 17)
plt.ylabel("Common prefix PDF", fontsize = 17)
plt.annotate('Consistency rate', fontsize = 17, xy=(26,0.575), xytext=(26,0.385), arrowprops=dict(facecolor='black', shrink=0.02))
print_fig_to_paper(output_type='png', plot_file_name='cp_bounded_delay', 
                    fig_font_size=16, fig_font_name='Times New Roman', 
                    fig_width=7, is_print=True, is_print_time=False)
plt.show()

# The success rate of eclipsed double spending in topological networks
x=[0.205, 0.3, 0.395]
y=[0.1114, 0.2478, 0.4155]
x0=[0.1, 0.195, 0.29, 0.385]
y0=[0.0308, 0.1098, 0.2426, 0.4067]
x1=[0.31, 0.405]
y1=[0.2514, 0.4121]
x2=[0.415]
y2=[0.4068]
xz=[0.1, 0.2, 0.3, 0.4]
z=[0.0298, 0.1162, 0.2495, 0.4126]
plt.rcParams["font.family"] = "Times new Roman"
plt.grid(True, linestyle='--', linewidth=0.5, color='Grey')
bar_width = 0.01
plt.bar(x0, y0, bar_width, edgecolor='#2A2A2A', linewidth=1, color=colors[4], label='No eclipsed miners')
plt.bar(x, y, bar_width, edgecolor='#2A2A2A', linewidth=1, color=colors[0], label='10% eclipsed miners')
plt.bar(x1, y1, bar_width, edgecolor='#2A2A2A', linewidth=1, color=colors[1], label='20% eclipsed miners')
plt.bar(x2, y2, bar_width, edgecolor='#2A2A2A', linewidth=1, color=colors[2], label='30% eclipsed miners')
plt.plot(xz, z, color=colors[3],linestyle='--',linewidth=1.5, label='theory')
plt.legend(loc="upper left", prop={"size": 16})
plt.xlabel('Adversary power ratio (With eclipsed miners)',fontsize = 16)
plt.ylabel('Attack success ratio',fontsize = 16)
plt.xlim([0.09, 0.425])
plt.ylim([0.01, 0.55])
print_fig_to_paper(output_type='png', plot_file_name='eclipse_doublespending', 
                    fig_font_size=16, fig_font_name='Times New Roman', 
                    fig_width=7, is_print=True, is_print_time=False)
plt.show()